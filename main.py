import asyncio
import json
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import ai.cuestionario as cuestionario
import ai.embeddings as embeddings
import ai.confianza as motor_confianza
import ai.evidencia as motor_evidencia
import tools.php_client as php_client
from ai import crear_proveedor
from config import settings, ruta_cita_con_especialidad, RUTAS_FRONTEND
from storage import init_db
from storage import auditoria, conocimiento, evidencia, memoria, propuestas, sesiones, validaciones
from storage.db import conectar as conectar_db, unidad_de_trabajo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("asistente")

proveedor = crear_proveedor()

# Referencias a tareas en segundo plano (evita que el GC las elimine).
_tareas_fondo: set[asyncio.Task] = set()


def _tarea_fondo(coro) -> asyncio.Task:
    tarea = asyncio.create_task(coro)
    _tareas_fondo.add(tarea)
    tarea.add_done_callback(_tareas_fondo.discard)
    return tarea

# Cuántos turnos previos se reenvían a Gemini en el flujo general.
MAX_HISTORIAL = 12
# Se pregunta la cédula una sola vez; si no la dan, se continúa sin historial.
MAX_INTENTOS_PACIENTE = 1
MAX_PREGUNTAS_GENERAL = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await proveedor.precargar_catalogo()
    except Exception:
        logger.exception("No se pudo precargar el catálogo al arrancar; se reintentará en cada consulta")

    async def _relay_periodico():
        while True:
            await asyncio.sleep(60)
            try:
                await auditoria.relay_auditoria()
            except Exception:
                logger.exception("Relay periódico de auditoría falló")

    tarea = asyncio.create_task(_relay_periodico())
    try:
        yield
    finally:
        tarea.cancel()
        with suppress(asyncio.CancelledError):
            await tarea


app = FastAPI(
    title="MIDI — CEM Jehová Rafa",
    description="Módulo Inteligente de Derivación e Información",
    version="2.0.0",
    lifespan=lifespan,
)

if settings.CORS_ORIGINS.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ConsultaIn(BaseModel):
    consulta: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    peticion_id: str | None = None


class ConocimientoIn(BaseModel):
    dominio: str
    ejemplo: str | None = None
    palabras_clave: list[str] = Field(default_factory=list)
    capa_error: str = "conocimiento"


class DecisionIn(BaseModel):
    decision: str
    motivo_codigo: str | None = None
    comentario: str | None = None
    version: int | None = None


class PropuestaIn(BaseModel):
    dominio: str
    tipo: str
    valor: str
    clave: str | None = None
    capa_error: str = "conocimiento"


class RechazoIn(BaseModel):
    motivo: str


ROLES_VALIDACION = {"10", "superadmin", "super usuario", "admin"}


def _usuario_validacion(request: Request) -> tuple[str, str]:
    actor = (request.headers.get("X-Usuario-Id") or "").strip()
    rol = (request.headers.get("X-Usuario-Rol") or "").strip()
    if not actor:
        raise HTTPException(400, "Falta X-Usuario-Id")
    if rol.lower() not in ROLES_VALIDACION:
        raise HTTPException(403, "Rol no autorizado para validar")
    return actor, rol


def verificar_api_key(x_api_key: str | None) -> None:
    esperada = settings.API_KEY_COMPARTIDA
    if not esperada:
        raise HTTPException(status_code=503, detail="Servicio no configurado")
    if not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(status_code=401, detail="API key inválida")


def _datos_usuario(request: Request) -> dict:
    return {
        "id": request.headers.get("X-Usuario-Id"),
        "rol": request.headers.get("X-Usuario-Rol"),
        "nombre": request.headers.get("X-Usuario-Nombre"),
    }


def _extraer_cedula(texto: str) -> str | None:
    m = re.search(r"\b([1-9][0-9]{6,7}(?:-R[0-9]{1,2})?)\b", texto or "")
    return m.group(1) if m else None


def _accion(especialidad: str | None) -> dict:
    if not especialidad:
        return {"etiqueta": "", "ruta": "", "visible": False}
    return {
        "etiqueta": f"Agendar cita con {especialidad}",
        "ruta": ruta_cita_con_especialidad(especialidad),
        "visible": True,
    }


def _respuesta_pregunta(texto: str, estado: dict, progreso: int | None = None) -> dict:
    return {
        "tipo_respuesta": "aclaracion",
        "mensaje": "Necesito un poco más de información para orientar mejor.",
        "especialidad_sugerida": None,
        "especialidades_disponibles": [],
        "pregunta_aclaratoria": texto,
        "pregunta_activa": texto,
        "posibles_asociaciones": [],
        "a_descartar": [],
        "pruebas_sugeridas": [],
        "recomendacion": "",
        "observacion": "",
        "modulo_sugerido": None,
        "progreso": progreso if progreso is not None else cuestionario.progreso(estado),
        "informacion_recopilada": estado.get("respuestas", {}),
        "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
    }


def _respuesta_emergencia() -> dict:
    return {
        "tipo_respuesta": "emergencia",
        "mensaje": (
            "Los datos describen posibles señales de alarma. Recomiendo acudir de "
            "inmediato al área de Emergencia o contactar al médico de guardia."
        ),
        "especialidad_sugerida": None,
        "especialidades_disponibles": [],
        "pregunta_aclaratoria": "",
        "pregunta_activa": "",
        "posibles_asociaciones": [],
        "a_descartar": [],
        "pruebas_sugeridas": [],
        "recomendacion": "Acudir de inmediato a Emergencia.",
        "observacion": "",
        "modulo_sugerido": None,
        "progreso": 100,
        "informacion_recopilada": {},
        "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
    }


async def _resolver_paciente(estado: dict, texto: str, usuario: dict) -> None:
    estado["siguiente_pregunta"] = None
    cedula = _extraer_cedula(texto)
    q = cedula or (texto or "").strip()

    if len(q) < 2:
        return

    resultados = await php_client.buscar_paciente(q)
    if not resultados:
        return

    elegido = None
    if cedula:
        elegido = next((p for p in resultados if str(p.get("cedula")) == cedula), None)
    if elegido is None and len(resultados) == 1:
        elegido = resultados[0]
    if elegido is None:
        return

    estado["paciente_id"] = elegido.get("id_paciente")
    estado["paciente_cedula"] = elegido.get("cedula")
    estado["paciente_nombre"] = (
        f"{elegido.get('nombre', '')} {elegido.get('apellido', '')}".strip()
    )
    await _cargar_contexto(estado, usuario)


async def _cargar_contexto(estado: dict, usuario: dict) -> None:
    """Carga controles/patologías, usando la memoria por usuario/paciente."""
    pid = estado.get("paciente_id")
    if not pid:
        return

    guardada = await memoria.obtener(usuario["id"], pid)
    if guardada and guardada.get("datos"):
        estado["contexto"] = guardada["datos"]
        estado["contexto_cargado"] = True
        # Si la memoria existe pero aún no tiene embedding (p. ej. base antigua
        # o fallo previo), lo generamos en segundo plano.
        if not guardada.get("embedding"):
            _tarea_fondo(_indexar_memoria(usuario["id"], pid, guardada.get("resumen", "")))
        return

    controles, patologias = await asyncio.gather(
        php_client.get_controles_paciente(int(pid)),
        php_client.get_patologias_paciente(int(pid)),
    )
    estado["contexto"] = {"controles": controles, "patologias": patologias}
    estado["contexto_cargado"] = True

    resumen = cuestionario.resumen_contexto(estado["contexto"])
    await memoria.guardar(usuario["id"], pid, resumen, estado["contexto"])

    # El embedding se calcula en segundo plano para no retrasar la respuesta.
    _tarea_fondo(_indexar_memoria(usuario["id"], pid, resumen))


async def _indexar_memoria(id_usuario: str, id_paciente, resumen: str) -> None:
    logger.info("Indexando memoria (usuario=%s paciente=%s)", id_usuario, id_paciente)
    vector = await embeddings.embed(resumen)
    logger.info("Embedding obtenido: %s", len(vector) if vector else None)
    if vector:
        await memoria.actualizar_embedding(id_usuario, id_paciente, vector)


async def _finalizar(estado: dict, usuario: dict) -> dict:
    catalogo = php_client.get_catalogo_cache_sincrono()
    ficha = cuestionario.construir_ficha(estado, estado.get("contexto", {}), catalogo)

    try:
        respuesta = await proveedor.orientar(ficha, historial=None)
    except Exception:
        logger.exception("Fallo al redactar la orientación final")
        respuesta = {
            "tipo_respuesta": "orientacion",
            "mensaje": "Con lo recopilado, conviene una valoración médica presencial.",
            "especialidad_sugerida": None,
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "posibles_asociaciones": [],
            "a_descartar": [],
            "pruebas_sugeridas": [],
            "recomendacion": "",
            "observacion": "",
            "modulo_sugerido": None,
            "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
        }

    candidata = cuestionario.especialidad_candidata(estado, catalogo)
    cfg = cuestionario.dominios().get(estado.get("dominio"), {})

    if respuesta.get("tipo_respuesta") != "emergencia":
        respuesta["tipo_respuesta"] = "orientacion"

    if not respuesta.get("especialidad_sugerida"):
        respuesta["especialidad_sugerida"] = candidata

    if not respuesta.get("pruebas_sugeridas"):
        respuesta["pruebas_sugeridas"] = cfg.get("pruebas", [])

    if not respuesta.get("posibles_asociaciones"):
        respuesta["posibles_asociaciones"] = cfg.get("posibles_asociaciones", [])

    if not respuesta.get("a_descartar"):
        respuesta["a_descartar"] = cfg.get("a_descartar", [])

    if not respuesta.get("recomendacion") and candidata:
        respuesta["recomendacion"] = f"Agendar una cita con {candidata} para valoración."

    respuesta["accion_sugerida"] = _accion(respuesta.get("especialidad_sugerida"))
    respuesta["pregunta_activa"] = ""
    respuesta["pregunta_aclaratoria"] = ""
    respuesta["progreso"] = 100
    respuesta["informacion_recopilada"] = estado.get("respuestas", {})

    estado["completo"] = True
    return respuesta


async def _flujo_cuestionario(consulta: str, estado: dict, usuario: dict) -> dict:
    cfg = cuestionario.dominios().get(estado.get("dominio"), {})

    # 1) Si había una pregunta pendiente, registrar la respuesta.
    pendiente = estado.get("siguiente_pregunta")
    if pendiente == "__paciente__":
        await _resolver_paciente(estado, consulta, usuario)
    elif pendiente:
        cuestionario.registrar_respuesta(estado, consulta)
        estado["siguiente_pregunta"] = None

    # 2) Señales de alarma: emergencia inmediata (sin más preguntas).
    textos = [estado.get("motivo", "")] + list(estado.get("respuestas", {}).values())
    if any(cuestionario.hay_alarma(t, estado["dominio"]) for t in textos):
        estado["completo"] = True
        return _respuesta_emergencia()

    # 3) Identificar al paciente (una vez; si no, se pregunta la cédula).
    if not estado.get("paciente_id") and not estado.get("paciente_omitido"):
        if not estado.get("_intento_inicial"):
            estado["_intento_inicial"] = True
            # Solo intentamos resolverlo de entrada si el motivo trae una cédula.
            if _extraer_cedula(estado.get("motivo", "")):
                await _resolver_paciente(estado, estado.get("motivo", ""), usuario)

        if not estado.get("paciente_id"):
            if estado.get("intentos_paciente", 0) < MAX_INTENTOS_PACIENTE:
                estado["siguiente_pregunta"] = "__paciente__"
                estado["intentos_paciente"] = estado.get("intentos_paciente", 0) + 1
                return _respuesta_pregunta(
                    "Si desea que revise los antecedentes del paciente, indíqueme su cédula; "
                    "si no, escriba «continuar».",
                    estado,
                )
            estado["paciente_omitido"] = True

    # 4) ¿Ya hay información suficiente?
    if cuestionario.es_suficiente(estado) or len(estado.get("preguntas_hechas", [])) >= cfg.get("max_preguntas", 5):
        return await _finalizar(estado, usuario)

    # 5) Siguiente pregunta del dominio.
    pregunta = cuestionario.proxima_pregunta(estado)
    if not pregunta:
        return await _finalizar(estado, usuario)

    estado["siguiente_pregunta"] = pregunta["id"]
    return _respuesta_pregunta(pregunta["texto"], estado)


async def _flujo_general(consulta: str, historial_previo: list[dict], estado: dict) -> dict:
    """Flujo con Gemini para síntomas fuera de los dominios del cuestionario."""
    usadas = int(estado.get("preguntas_generales", 0))

    if usadas >= MAX_PREGUNTAS_GENERAL:
        return await _cierre_general(consulta, historial_previo, estado)

    respuesta = await proveedor.orientar(consulta, historial=historial_previo or None)

    if respuesta.get("tipo_respuesta") == "aclaracion":
        usadas += 1
        estado["preguntas_generales"] = usadas
        # Se reserva el 100% para el cierre.
        respuesta["progreso"] = min(90, int(round(100 * usadas / MAX_PREGUNTAS_GENERAL)))
    else:
        estado["completo"] = True

    return respuesta


async def _cierre_general(consulta: str, historial_previo: list[dict], estado: dict) -> dict:
    """Fuerza la conclusión cuando ya se hicieron demasiadas preguntas."""
    directiva = (
        "CIERRE DE CONSULTA. No hagas más preguntas. Con la conversación previa y "
        f"esta última respuesta (\"{consulta}\"), entrega la orientación final: "
        "especialidad del catálogo, posibles asociaciones, a descartar y pruebas "
        "sugeridas. Si no hay una especialidad clara, responde tipo catalogo."
    )

    try:
        respuesta = await proveedor.orientar(directiva, historial=historial_previo or None)
    except Exception:
        logger.exception("Fallo al cerrar la consulta general")
        respuesta = {
            "tipo_respuesta": "derivar",
            "mensaje": "No pude conectar con el modelo de IA para cerrar la orientación.",
            "especialidad_sugerida": None,
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "posibles_asociaciones": [],
            "a_descartar": [],
            "pruebas_sugeridas": [],
            "recomendacion": "",
            "observacion": "",
            "modulo_sugerido": None,
            "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
        }

    if respuesta.get("tipo_respuesta") == "aclaracion":
        catalogo = php_client.get_catalogo_cache_sincrono()
        candidata = next(
            (c["nombre"] for c in catalogo if "consulta general" in c.get("nombre", "").lower()),
            None,
        )
        respuesta["tipo_respuesta"] = "orientacion" if candidata else "derivar"
        respuesta["especialidad_sugerida"] = candidata
        respuesta["pregunta_aclaratoria"] = ""
        respuesta["pregunta_activa"] = ""
        if candidata:
            respuesta["recomendacion"] = f"Agendar una valoración con {candidata}."
        respuesta["accion_sugerida"] = _accion(candidata)

    respuesta["progreso"] = 100
    estado["completo"] = True
    return respuesta


async def _procesar(consulta: str, historial_previo: list[dict], estado: dict, usuario: dict) -> dict:
    # Si la sesión ya cerró un cuestionario, cada mensaje nuevo inicia otra consulta.
    if estado.get("completo"):
        estado.clear()

    if not estado.get("dominio"):
        # Si ya empezó el flujo general (ya hizo preguntas), no cambiamos de
        # dominio a mitad de conversación: eso reiniciaría y repetiría todo.
        if int(estado.get("preguntas_generales", 0)) > 0:
            return await _flujo_general(consulta, historial_previo, estado)

        dominio = cuestionario.detectar_dominio(consulta)
        if dominio:
            estado.clear()
            estado.update(cuestionario.nueva_sesion(dominio, consulta))
            # El aprendizaje implícito se retiró: las frases nuevas entran como
            # propuestas revisables (`POST /conocimiento`), no a la KB activa.
        else:
            return await _flujo_general(consulta, historial_previo, estado)

    return await _flujo_cuestionario(consulta, estado, usuario)


@app.get("/")
def raiz():
    return {"servicio": "midi-clinica", "estado": "ok"}


@app.post("/orientar")
async def orientar(
    body: ConsultaIn,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    usuario = _datos_usuario(request)
    session_id = body.session_id or str(uuid4())
    t0 = time.perf_counter()

    sesion = await sesiones.obtener_sesion(session_id)
    if sesion is None:
        sesion = await sesiones.crear_sesion(session_id, usuario["id"])
    estado = sesion.get("estado") or {}

    if body.peticion_id:
        peticion_id = body.peticion_id
    else:
        # Compatibilidad mientras el frontend PHP no envía la clave.
        peticion_id = str(uuid4())
        logger.warning("Petición sin peticion_id (session=%s); se generó uno", session_id)

    turno_previo = None
    if body.peticion_id:
        turno_previo = await sesiones.obtener_turno_por_peticion(peticion_id)
        if turno_previo:
            if turno_previo["consulta_session_id"] != session_id:
                raise HTTPException(
                    409, "peticion_id ya usado en otra sesión"
                )
            if turno_previo.get("respuesta_json"):
                try:
                    previa = json.loads(turno_previo["respuesta_json"])
                except ValueError:
                    previa = None
                if isinstance(previa, dict):
                    return {**previa, "idempotente": True}

    if turno_previo:
        # Reintento tras un cierre: se reutiliza el caso original.
        consulta = {"id": turno_previo["consulta_id"]}
    else:
        consulta = await sesiones.obtener_o_crear_consulta(session_id, usuario["id"])

    try:
        turno = await sesiones.crear_turno(
            consulta["id"], peticion_id, body.consulta, "user"
        )
    except sesiones.PeticionIdConflicto:
        raise HTTPException(409, "peticion_id ya usado en otra consulta")

    historial_previo = await sesiones.historial_para_gemini(session_id, MAX_HISTORIAL)
    mensaje_usuario_id = await sesiones.agregar_mensaje(
        session_id, "user", body.consulta, consulta["id"], turno["id"]
    )

    logger.info(
        "Consulta (session=%s consulta=%s turno=%s usuario=%r rol=%r id=%r "
        "len=%d hash=%s)",
        session_id, consulta["id"], turno["id"], usuario["nombre"],
        usuario["rol"], usuario["id"], len(body.consulta),
        evidencia.hash_texto(body.consulta)[:12],
    )

    degradado = False
    token_usuario = php_client.usuario_actual.set(usuario["id"])
    try:
        respuesta = await _procesar(body.consulta, historial_previo, estado, usuario)
    except Exception:
        degradado = True
        logger.exception("Fallo al procesar la consulta (session=%s)", session_id)
        respuesta = {
            "tipo_respuesta": "derivar",
            "mensaje": (
                "No pude conectar con el modelo de IA en este momento. "
                "Intenta de nuevo en unos segundos o revisa el catálogo de especialidades."
            ),
            "especialidad_sugerida": None,
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "posibles_asociaciones": [],
            "a_descartar": [],
            "pruebas_sugeridas": [],
            "recomendacion": "",
            "observacion": "",
            "modulo_sugerido": None,
            "accion_sugerida": {
                "etiqueta": "Ver especialidades",
                "ruta": RUTAS_FRONTEND["especialidades"],
                "visible": True,
            },
        }
    finally:
        php_client.usuario_actual.reset(token_usuario)

    # Guardamos también la pregunta para que el historial no la pierda y el
    # modelo no repita lo mismo en el siguiente turno.
    texto_asistente = (respuesta.get("mensaje") or "").strip()
    pregunta = respuesta.get("pregunta_activa") or respuesta.get("pregunta_aclaratoria")
    if pregunta:
        texto_asistente = f"{texto_asistente}\n{pregunta}".strip()

    tipo_respuesta = respuesta.get("tipo_respuesta")
    origen_respuesta = "cuestionario" if estado.get("dominio") else "llm"
    dominio = estado.get("dominio")
    especialidad = respuesta.get("especialidad_sugerida")
    respuestas = estado.get("respuestas", {})

    motivo_texto = estado.get("motivo") or body.consulta
    candidatos = cuestionario.detectar_candidatos(motivo_texto)
    top1 = float(candidatos[0]["score"]) if candidatos else 0.0
    top2 = float(candidatos[1]["score"]) if len(candidatos) > 1 else 0.0
    min_preguntas = (
        cuestionario.dominios().get(dominio) or {}
    ).get("min_preguntas", 3)

    componentes = motor_confianza.componentes(
        top1=top1,
        top2=top2,
        n_candidatos=len(candidatos),
        respondidas=len(respuestas),
        min_preguntas=min_preguntas,
        negaciones=motor_evidencia.contar_negaciones(motivo_texto),
    )
    confianza_total = motor_confianza.calcular(componentes)
    margen_top = motor_confianza.margen(top1, top2)
    revision, motivo_revision = motor_confianza.evaluar(
        total=confianza_total,
        margen_top=margen_top,
        n_candidatos=len(candidatos),
        tipo_respuesta=tipo_respuesta,
    )

    motivos = [m for m in (motivo_revision or "").split(",") if m]
    if motor_confianza.es_muestra(turno["id"]):
        motivos.append("muestra_dorada")
    if degradado:
        motivos.append("degradado")

    # La revisión es opcional y posterior: no bloquea la respuesta.
    if tipo_respuesta == "aclaracion":
        revision = False
        motivo_revision = None
    elif motivos:
        revision = True
        motivo_revision = ",".join(dict.fromkeys(motivos))
    else:
        motivo_revision = None

    resumen_ficha = {
        "motivo": estado.get("motivo"),
        "dominio": dominio,
        "respuestas": respuestas,
        "especialidad": especialidad,
        "controles": (estado.get("contexto") or {}).get("controles", []),
        "patologias": (estado.get("contexto") or {}).get("patologias", []),
    }
    latencia = int((time.perf_counter() - t0) * 1000)

    try:
        async with unidad_de_trabajo() as db:
            await sesiones.guardar_estado(session_id, estado, db=db)
            mensaje_asistente_id = await sesiones.agregar_mensaje(
                session_id, "model", texto_asistente,
                consulta["id"], turno["id"], db=db,
            )

            salida = {
                "session_id": session_id,
                "consulta_id": consulta["id"],
                "turno_id": turno["id"],
                "peticion_id": peticion_id,
                "mensaje_usuario_id": mensaje_usuario_id,
                "mensaje_id": mensaje_asistente_id,
                **respuesta,
            }

            evidencia_id = await evidencia.guardar_evidencia(
                db,
                turno_id=turno["id"],
                consulta_id=consulta["id"],
                resumen_ficha=resumen_ficha,
                respuesta_final=texto_asistente,
                componentes=componentes,
                candidatos=candidatos,
                revision_requerida=revision,
                motivo_revision=motivo_revision,
                confianza_total=confianza_total,
                modelo=getattr(proveedor, "nombre_modelo", settings.MODELO_GEMINI),
                catalogo_nombre=especialidad,
            )

            if revision:
                await evidencia.crear_validacion(
                    db,
                    consulta_id=consulta["id"],
                    evidencia_turno_id=evidencia_id,
                    motivo=motivo_revision or "confianza_baja",
                )

            await sesiones.actualizar_turno(
                turno["id"], tipo_respuesta, origen_respuesta, degradado,
                respuesta_json=salida, db=db,
            )

            await sesiones.actualizar_consulta(
                consulta["id"],
                flujo="cuestionario" if dominio else "general",
                dominio_id=conocimiento.id_dominio(dominio) if dominio else None,
                id_paciente=estado.get("paciente_id"),
                db=db,
            )

            # `aclaracion` mantiene la consulta abierta; el resto la cierra.
            if tipo_respuesta and tipo_respuesta != "aclaracion":
                await sesiones.cerrar_consulta(
                    consulta["id"], tipo_respuesta, db=db
                )

            await auditoria.registrar(
                {
                    "session_id": session_id,
                    "consulta_id": consulta["id"],
                    "turno_id": turno["id"],
                    "usuario_id": usuario["id"],
                    "usuario_rol": usuario["rol"],
                    "usuario_nombre": usuario["nombre"],
                    "paciente_id": estado.get("paciente_id"),
                    "dominio": dominio,
                    "consulta": body.consulta,
                    "tipo_respuesta": tipo_respuesta,
                    "especialidad_sugerida": especialidad,
                    "pruebas_sugeridas": respuesta.get("pruebas_sugeridas"),
                    "modelo_usado": getattr(
                        proveedor, "nombre_modelo", settings.MODELO_GEMINI
                    ),
                    "latencia_ms": latencia,
                    "tools_usadas": "cuestionario" if dominio else "gemini",
                    "json_respuesta": respuesta,
                    "resultado": "degradado" if degradado else "ok",
                },
                db=db,
                idempotency_key=f"turno:{turno['id']}",
            )
    except Exception:
        logger.exception(
            "Fallo al guardar el turno de forma durable "
            "(session=%s turno=%s)", session_id, turno["id"],
        )
        raise HTTPException(
            503,
            "No se pudo guardar el turno; reintenta con el mismo peticion_id",
        )

    try:
        await auditoria.relay_auditoria()
    except Exception:
        logger.exception("Relay de auditoría falló; se reintentará")

    return salida


@app.get("/sesiones/{session_id}")
async def ver_sesion(
    session_id: str,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    sesion = await sesiones.obtener_sesion(session_id)
    if sesion is None:
        raise HTTPException(404, "Sesión no encontrada")

    mensajes = await sesiones.listar_mensajes(session_id, 200)
    return {"session_id": session_id, "estado": sesion["estado"], "historial": mensajes}


@app.delete("/sesiones/{session_id}", status_code=204)
async def borrar_sesion(
    session_id: str,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    await sesiones.borrar_sesion(session_id)
    return None


@app.get("/auditoria")
async def ver_auditoria(
    limite: int = 50,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    return await auditoria.listar(limite)


@app.get("/validaciones")
async def listar_validaciones(
    request: Request,
    estado: str | None = None,
    especialidad: str | None = None,
    dominio: str | None = None,
    confianza_min: float | None = None,
    fecha: str | None = None,
    cursor: str | None = None,
    limite: int = 20,
):
    _usuario_validacion(request)
    try:
        return await validaciones.listar(
            estado=estado,
            especialidad=especialidad,
            dominio=dominio,
            confianza_min=confianza_min,
            fecha=fecha,
            cursor=cursor,
            limite=limite,
        )
    except validaciones.MotivoRequerido as exc:
        raise HTTPException(422, str(exc))


@app.get("/validaciones/{validacion_id}")
async def detalle_validacion(validacion_id: int, request: Request):
    _usuario_validacion(request)
    datos = await validaciones.detalle(validacion_id)
    if not datos:
        raise HTTPException(404, "Validación no encontrada")
    return datos


@app.post("/validaciones/{validacion_id}/tomar")
async def tomar_validacion(validacion_id: int, request: Request):
    actor, _ = _usuario_validacion(request)
    try:
        return await validaciones.tomar(validacion_id, actor)
    except validaciones.ValidacionNoEncontrada:
        raise HTTPException(404, "Validación no encontrada")
    except validaciones.ConflictoValidacion as exc:
        raise HTTPException(409, {"error": "conflicto", **exc.detalle})


@app.post("/validaciones/{validacion_id}/decidir")
async def decidir_validacion(
    validacion_id: int, body: DecisionIn, request: Request
):
    actor, _ = _usuario_validacion(request)
    try:
        return await validaciones.decidir(
            validacion_id,
            actor,
            body.decision,
            body.motivo_codigo,
            body.comentario,
            body.version,
        )
    except validaciones.ValidacionNoEncontrada:
        raise HTTPException(404, "Validación no encontrada")
    except validaciones.MotivoRequerido as exc:
        raise HTTPException(422, str(exc))
    except validaciones.ConflictoValidacion as exc:
        raise HTTPException(409, {"error": "conflicto", **exc.detalle})


@app.post("/validaciones/{validacion_id}/visto")
async def visto_validacion(validacion_id: int, request: Request):
    actor, rol = _usuario_validacion(request)
    try:
        return await validaciones.visto(validacion_id, actor, rol)
    except validaciones.ValidacionNoEncontrada:
        raise HTTPException(404, "Validación no encontrada")


@app.get("/propuestas")
async def listar_propuestas(
    request: Request,
    estado: str | None = None,
    dominio: str | None = None,
    limite: int = 50,
):
    _usuario_validacion(request)
    return await propuestas.listar(
        estado=estado, dominio=dominio, limite=limite
    )


@app.post("/propuestas")
async def crear_propuesta(body: PropuestaIn, request: Request):
    actor, _ = _usuario_validacion(request)
    try:
        propuesta_id = await propuestas.crear(
            dominio_clave=body.dominio,
            tipo=body.tipo,
            valor=body.valor,
            clave=body.clave,
            capa_error=body.capa_error,
            generado_por=actor,
        )
    except propuestas.ConflictoPropuesta as exc:
        raise HTTPException(422, str(exc))
    return {"ok": propuesta_id is not None, "propuesta_id": propuesta_id}


@app.post("/propuestas/{propuesta_id}/aprobar")
async def aprobar_propuesta(propuesta_id: int, request: Request):
    actor, _ = _usuario_validacion(request)
    try:
        return await propuestas.aprobar(propuesta_id, actor)
    except propuestas.PropuestaNoEncontrada:
        raise HTTPException(404, "Propuesta no encontrada")
    except propuestas.Autoaprobacion as exc:
        raise HTTPException(409, str(exc))
    except propuestas.ConflictoPropuesta as exc:
        raise HTTPException(409, str(exc))


@app.post("/propuestas/{propuesta_id}/rechazar")
async def rechazar_propuesta(
    propuesta_id: int, body: RechazoIn, request: Request
):
    actor, _ = _usuario_validacion(request)
    try:
        return await propuestas.rechazar(propuesta_id, actor, body.motivo)
    except propuestas.PropuestaNoEncontrada:
        raise HTTPException(404, "Propuesta no encontrada")
    except propuestas.ConflictoPropuesta as exc:
        raise HTTPException(409, str(exc))


@app.get("/salud")
async def salud():
    con = await conectar_db()
    try:
        async with con.execute("PRAGMA foreign_key_check") as cur:
            fk = [dict(f) for f in await cur.fetchall()]
        async with con.execute(
            "SELECT id, hash FROM kb_version WHERE activa = 1 LIMIT 1"
        ) as cur:
            version = await cur.fetchone()
        async with con.execute(
            "SELECT COUNT(*) FROM validacion WHERE estado = 'pendiente'"
        ) as cur:
            pendientes = (await cur.fetchone())[0]
        async with con.execute(
            "SELECT COUNT(*) FROM propuesta_conocimiento "
            "WHERE estado = 'pendiente'"
        ) as cur:
            propuestas_pendientes = (await cur.fetchone())[0]
    finally:
        await con.close()

    return {
        "ok": not fk,
        "foreign_key_check": fk,
        "kb_version": dict(version) if version else None,
        "validaciones_pendientes": pendientes,
        "propuestas_pendientes": propuestas_pendientes,
    }


@app.get("/conocimiento")
async def ver_conocimiento(x_api_key: str | None = Header(default=None)):
    """Devuelve lo que MIDI ha aprendido (ejemplos/palabras por dominio)."""
    verificar_api_key(x_api_key)
    return cuestionario.listar_aprendido()


@app.post("/conocimiento")
async def aprender_conocimiento(
    body: ConocimientoIn,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Registra conocimiento nuevo como propuestas revisables."""
    verificar_api_key(x_api_key)

    if body.dominio not in cuestionario.dominios():
        raise HTTPException(status_code=404, detail="Dominio no encontrado")

    actor = (request.headers.get("X-Usuario-Id") or "").strip() or None
    creadas: list[int] = []

    if body.ejemplo:
        propuesta_id = await propuestas.crear(
            dominio_clave=body.dominio,
            tipo="ejemplo",
            valor=body.ejemplo,
            capa_error=body.capa_error,
            generado_por=actor,
        )
        if propuesta_id:
            creadas.append(propuesta_id)

    for palabra in body.palabras_clave or []:
        propuesta_id = await propuestas.crear(
            dominio_clave=body.dominio,
            tipo="palabra",
            valor=palabra,
            capa_error=body.capa_error,
            generado_por=actor,
        )
        if propuesta_id:
            creadas.append(propuesta_id)

    return {
        "ok": True,
        "dominio": body.dominio,
        "pendiente": len(creadas),
        "propuestas": creadas,
    }


@app.get("/memoria/similares")
async def memoria_similares(
    request: Request,
    q: str,
    k: int = 5,
    x_api_key: str | None = Header(default=None),
):
    """Memoria vectorizada: memorias del usuario más parecidas a la consulta."""
    verificar_api_key(x_api_key)
    usuario = _datos_usuario(request)
    if not usuario["id"]:
        raise HTTPException(status_code=400, detail="Usuario no identificado")

    vector = await embeddings.embed(q)
    if not vector:
        return {"ok": False, "resultados": []}

    return {
        "ok": True,
        "resultados": await memoria.buscar_similares(usuario["id"], vector, k),
    }


@app.delete("/memoria", status_code=204)
async def borrar_memoria(
    request: Request,
    id_paciente: str | None = None,
    x_api_key: str | None = Header(default=None),
):
    verificar_api_key(x_api_key)
    usuario = _datos_usuario(request)
    if not usuario["id"]:
        raise HTTPException(status_code=400, detail="Usuario no identificado")
    await memoria.borrar(usuario["id"], id_paciente)
    return None

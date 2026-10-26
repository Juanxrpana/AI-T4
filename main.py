import asyncio
import logging
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import ai.cuestionario as cuestionario
import tools.php_client as php_client
from ai import ProveedorGemini
from config import settings, ruta_cita_con_especialidad, RUTAS_FRONTEND
from storage import init_db
from storage import auditoria, memoria, sesiones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("asistente")

proveedor = ProveedorGemini()

# Cuántos turnos previos se reenvían a Gemini en el flujo general.
MAX_HISTORIAL = 12
MAX_INTENTOS_PACIENTE = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await proveedor.precargar_catalogo()
    except Exception:
        logger.exception("No se pudo precargar el catálogo al arrancar; se reintentará en cada consulta")
    yield


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
    m = re.search(r"\b(\d{6,10})\b", texto or "")
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
        return

    controles, patologias = await asyncio.gather(
        php_client.get_controles_paciente(int(pid)),
        php_client.get_patologias_paciente(int(pid)),
    )
    estado["contexto"] = {"controles": controles, "patologias": patologias}
    estado["contexto_cargado"] = True

    resumen = cuestionario.resumen_contexto(estado["contexto"])
    await memoria.guardar(usuario["id"], pid, resumen, estado["contexto"])


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
                    "¿Me confirma la cédula o el nombre del paciente para revisar sus antecedentes?",
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


async def _procesar(consulta: str, historial_previo: list[dict], estado: dict, usuario: dict) -> dict:
    # Si la sesión ya cerró un cuestionario, cada mensaje nuevo inicia otra consulta.
    if estado.get("completo"):
        estado.clear()

    if not estado.get("dominio"):
        dominio = cuestionario.detectar_dominio(consulta)
        if dominio:
            estado.clear()
            estado.update(cuestionario.nueva_sesion(dominio, consulta))
        else:
            return await proveedor.orientar(consulta, historial=historial_previo or None)

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

    historial_previo = await sesiones.historial_para_gemini(session_id, MAX_HISTORIAL)
    await sesiones.agregar_mensaje(session_id, "user", body.consulta)

    logger.info(
        "Consulta (session=%s usuario=%r rol=%r id=%r): %.80s",
        session_id, usuario["nombre"], usuario["rol"], usuario["id"], body.consulta,
    )

    token_usuario = php_client.usuario_actual.set(usuario["id"])
    try:
        respuesta = await _procesar(body.consulta, historial_previo, estado, usuario)
    except Exception:
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

    await sesiones.guardar_estado(session_id, estado)
    await sesiones.agregar_mensaje(session_id, "model", respuesta.get("mensaje", ""))

    latencia = int((time.perf_counter() - t0) * 1000)
    try:
        await auditoria.registrar({
            "session_id": session_id,
            "usuario_id": usuario["id"],
            "usuario_rol": usuario["rol"],
            "usuario_nombre": usuario["nombre"],
            "paciente_id": estado.get("paciente_id"),
            "dominio": estado.get("dominio"),
            "consulta": body.consulta,
            "tipo_respuesta": respuesta.get("tipo_respuesta"),
            "especialidad_sugerida": respuesta.get("especialidad_sugerida"),
            "pruebas_sugeridas": respuesta.get("pruebas_sugeridas"),
            "modelo_usado": settings.MODELO_GEMINI,
            "latencia_ms": latencia,
            "tools_usadas": "cuestionario" if estado.get("dominio") else "gemini",
            "json_respuesta": respuesta,
        })
    except Exception:
        logger.exception("No se pudo registrar la auditoría")

    return {"session_id": session_id, **respuesta}


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

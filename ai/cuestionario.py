"""Motor del cuestionario guiado (híbrido, determinista).

Las reglas de este módulo deciden **qué preguntar y cuándo terminar**. Gemini
solo se usa al final para redactar la orientación. La base de conocimiento
curada vive en SQLite (`storage/conocimiento.py`); los JSON de `knowledge/`
son solo semilla de migración.

Aprendizaje:
- Los ejemplos y palabras que se añaden desde `/conocimiento` se guardan en
  SQLite con `origen = 'aprendido'`. La ruta automática de aprendizaje se
  retiró: en Fase 3 todo cambio pasa por propuestas revisables.
- Las frases parecidas se reconocen por similitud de tokens aunque no
  contengan una palabra clave exacta.
"""

import ai.evidencia as evidencia
from storage import conocimiento

# Alias de compatibilidad: la implementación vive en ai.evidencia.
_VACIAS = evidencia.VACIAS


def _normalizar(texto: str) -> str:
    return evidencia.normalizar(texto)


def dominios() -> dict:
    """Snapshot de la KB activa en SQLite (con respaldo JSON al arrancar)."""
    return conocimiento.snapshot_sincrono()


def _tokens(texto: str) -> set[str]:
    return evidencia.tokens(texto)


def _similitud(a: str, b: str) -> float:
    return evidencia.similitud(a, b)


_UMBRAL_EJEMPLO = 0.60


def detectar_candidatos(texto: str, limite: int = 3) -> list[dict]:
    """Ranking de dominios por palabra clave positiva o ejemplo parecido."""
    resultados: list[dict] = []
    for clave, cfg in dominios().items():
        if evidencia.coincide(texto, cfg.get("palabras_clave", [])):
            score = 1.0
        else:
            score = max(
                (_similitud(texto, ejemplo) for ejemplo in cfg.get("ejemplos", [])),
                default=0.0,
            )
        if score > 0:
            resultados.append({
                "dominio": clave,
                "dominio_id": cfg.get("_id"),
                "score": round(score, 4),
            })

    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados[:limite]


def detectar_dominio(texto: str) -> str | None:
    """Primer candidato que supera el umbral de ejemplo o tiene keyword."""
    for candidato in detectar_candidatos(texto):
        if candidato["score"] >= _UMBRAL_EJEMPLO:
            return candidato["dominio"]
    return None


def aprender_ejemplo(dominio: str, frase: str) -> bool:
    """Guarda una frase real del usuario como ejemplo aprendido del dominio."""
    if dominio not in dominios():
        return False
    return conocimiento.agregar_ejemplo(dominio, frase)


def aprender_palabras(dominio: str, palabras: list[str]) -> bool:
    """Añade palabras clave manualmente al dominio."""
    if dominio not in dominios():
        return False

    agregado = False
    for palabra in palabras or []:
        if conocimiento.agregar_palabra(dominio, palabra):
            agregado = True
    return agregado


def listar_aprendido() -> dict:
    return conocimiento.listar_aprendido()


def nueva_sesion(dominio: str, motivo: str) -> dict:
    return {
        "dominio": dominio,
        "motivo": motivo,
        "paciente_id": None,
        "paciente_cedula": None,
        "paciente_nombre": None,
        "preguntas_hechas": [],
        "respuestas": {},
        "siguiente_pregunta": None,
        "contexto": {"controles": [], "patologias": []},
        "contexto_cargado": False,
        "completo": False,
    }


def hay_alarma(texto: str, dominio: str) -> bool:
    cfg = dominios().get(dominio, {})
    return evidencia.hay_alarma(texto, cfg.get("senal_alarma", []))


def proxima_pregunta(estado: dict) -> dict | None:
    cfg = dominios().get(estado.get("dominio"), {})
    hechas = set(estado.get("preguntas_hechas", []))

    if len(hechas) >= cfg.get("max_preguntas", 5):
        return None

    for pregunta in cfg.get("preguntas", []):
        if pregunta["id"] not in hechas:
            return pregunta

    return None


def registrar_respuesta(estado: dict, texto: str) -> None:
    pregunta = estado.get("siguiente_pregunta")
    if not pregunta:
        return
    estado.setdefault("respuestas", {})[pregunta] = texto
    estado.setdefault("preguntas_hechas", []).append(pregunta)
    estado["siguiente_pregunta"] = None


def es_suficiente(estado: dict) -> bool:
    cfg = dominios().get(estado.get("dominio"), {})
    return len(estado.get("preguntas_hechas", [])) >= cfg.get("min_preguntas", 3)


def progreso(estado: dict) -> int:
    cfg = dominios().get(estado.get("dominio"), {})
    minimo = max(1, cfg.get("min_preguntas", 3))
    hechas = len(estado.get("preguntas_hechas", []))
    return min(100, int(round(100 * hechas / minimo)))


def especialidad_candidata(estado: dict, catalogo: list[dict]) -> str | None:
    cfg = dominios().get(estado.get("dominio"), {})
    disponibles = {_normalizar(c.get("nombre", "")): c.get("nombre") for c in catalogo}

    for nombre in cfg.get("especialidades", []):
        real = disponibles.get(_normalizar(nombre))
        if real:
            return real

    return disponibles.get(_normalizar("CONSULTA GENERAL"))


def resumen_contexto(contexto: dict) -> str:
    partes: list[str] = []

    patologias = contexto.get("patologias", [])
    if patologias:
        nombres = sorted({p.get("nombre_patologia", "").strip() for p in patologias if p.get("nombre_patologia")})
        if nombres:
            partes.append("Patologías: " + ", ".join(nombres))

    controles = contexto.get("controles", [])
    if controles:
        lineas = []
        for c in controles[:5]:
            fecha = (c.get("fecha_control") or "")[:10]
            diag = (c.get("diagnostico") or "").strip()
            meds = (c.get("medicamentosRecetados") or "").strip()
            sintomas = (c.get("sintomas") or "").strip()
            detalle = f"- {fecha}: diagnóstico previo '{diag}'"
            if sintomas:
                detalle += f"; síntomas: {sintomas}"
            if meds:
                detalle += f"; medicamentos indicados antes: {meds}"
            lineas.append(detalle)
        partes.append("Controles previos:\n" + "\n".join(lineas))

    return "\n".join(partes) if partes else "Sin antecedentes registrados en los últimos meses."


def construir_ficha(
    estado: dict,
    contexto: dict,
    catalogo: list[dict],
    recuerdos: list[str] | None = None,
) -> str:
    cfg = dominios().get(estado.get("dominio"), {})
    preguntas = {p["id"]: p["texto"] for p in cfg.get("preguntas", [])}

    respuestas = []
    for qid, valor in estado.get("respuestas", {}).items():
        respuestas.append(f"- {preguntas.get(qid, qid)}: {valor}")

    paciente = estado.get("paciente_nombre") or "No identificado"
    especialidad = especialidad_candidata(estado, catalogo) or "no determinada"

    texto = (
        "FICHA CLÍNICA COMPLETA. No hagas más preguntas: redacta la orientación final.\n"
        f"Dominio: {cfg.get('nombre', estado.get('dominio'))}\n"
        f"Paciente: {paciente}\n"
        f"Motivo inicial: {estado.get('motivo', '')}\n"
        "Respuestas del cuestionario:\n"
        + ("\n".join(respuestas) if respuestas else "- (sin respuestas)")
        + "\nAntecedentes del paciente:\n"
        + resumen_contexto(contexto)
    )

    if recuerdos:
        texto += "\nRecuerdos relevantes de consultas previas:\n" + "\n".join(
            f"- {r}" for r in recuerdos
        )

    return (
        texto
        + "\nEspecialidad candidata del catálogo: "
        + especialidad
        + "\nPruebas orientativas del dominio: "
        + ", ".join(cfg.get("pruebas", []))
    )

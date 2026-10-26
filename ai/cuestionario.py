"""Motor del cuestionario guiado (híbrido, determinista).

Las reglas de este módulo deciden **qué preguntar y cuándo terminar**. Gemini
solo se usa al final para redactar la orientación. La base de conocimiento vive
en `knowledge/dominios.json`.
"""

import json
import unicodedata
from pathlib import Path

_RUTA = Path("knowledge/dominios.json")
_dominios_cache: dict | None = None


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def dominios() -> dict:
    global _dominios_cache
    if _dominios_cache is None:
        _dominios_cache = json.loads(_RUTA.read_text(encoding="utf-8"))
    return _dominios_cache


def detectar_dominio(texto: str) -> str | None:
    """Devuelve la clave del dominio cuyas palabras clave aparecen en el texto."""
    plano = _normalizar(texto)
    for clave, cfg in dominios().items():
        for palabra in cfg.get("palabras_clave", []):
            if _normalizar(palabra) in plano:
                return clave
    return None


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
    plano = _normalizar(texto)
    return any(_normalizar(p) in plano for p in cfg.get("senal_alarma", []))


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
    """Guarda la respuesta a la pregunta pendiente y avanza."""
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
    """Primera especialidad del dominio que exista en el catálogo real."""
    cfg = dominios().get(estado.get("dominio"), {})
    disponibles = {_normalizar(c.get("nombre", "")): c.get("nombre") for c in catalogo}

    for nombre in cfg.get("especialidades", []):
        real = disponibles.get(_normalizar(nombre))
        if real:
            return real

    return disponibles.get(_normalizar("CONSULTA GENERAL"))


def resumen_contexto(contexto: dict) -> str:
    """Texto legible con patologías y controles para la ficha."""
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


def construir_ficha(estado: dict, contexto: dict, catalogo: list[dict]) -> str:
    cfg = dominios().get(estado.get("dominio"), {})
    preguntas = {p["id"]: p["texto"] for p in cfg.get("preguntas", [])}

    respuestas = []
    for qid, valor in estado.get("respuestas", {}).items():
        respuestas.append(f"- {preguntas.get(qid, qid)}: {valor}")

    paciente = estado.get("paciente_nombre") or "No identificado"
    especialidad = especialidad_candidata(estado, catalogo) or "no determinada"

    return (
        "FICHA CLÍNICA COMPLETA. No hagas más preguntas: redacta la orientación final.\n"
        f"Dominio: {cfg.get('nombre', estado.get('dominio'))}\n"
        f"Paciente: {paciente}\n"
        f"Motivo inicial: {estado.get('motivo', '')}\n"
        "Respuestas del cuestionario:\n"
        + ("\n".join(respuestas) if respuestas else "- (sin respuestas)")
        + "\nAntecedentes del paciente:\n"
        + resumen_contexto(contexto)
        + "\nEspecialidad candidata del catálogo: "
        + especialidad
        + "\nPruebas orientativas del dominio: "
        + ", ".join(cfg.get("pruebas", []))
    )

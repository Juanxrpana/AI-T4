"""Motor del cuestionario guiado (híbrido, determinista) + aprendizaje.

Las reglas de este módulo deciden **qué preguntar y cuándo terminar**. Gemini
solo se usa al final para redactar la orientación. La base de conocimiento
curada vive en `knowledge/dominios.json`; lo aprendido en conversaciones se
guarda aparte en `knowledge/aprendido.json` y se fusiona al cargar.

Aprendizaje:
- Cada vez que se inicia un dominio, se guarda la frase del usuario como
  `ejemplo`. En el futuro, frases parecidas se reconocen por similitud de
  tokens aunque no contengan una palabra clave exacta.
- También se pueden añadir palabras clave manualmente (API `/conocimiento`).
"""

import json
import re
import unicodedata
from pathlib import Path

from config import settings

_RUTA = Path("knowledge/dominios.json")
_RUTA_APRENDIDO = Path(settings.APRENDIZAJE_PATH)
_dominios_cache: dict | None = None

# Palabras que no aportan al comparar frases.
_VACIAS = {
    "de", "la", "el", "en", "con", "que", "por", "para", "los", "las", "un",
    "una", "unos", "unas", "y", "o", "mi", "me", "se", "al", "del", "es",
    "son", "tengo", "tiene", "como", "desde", "esta", "este", "hace", "dias",
    "día", "hola", "problema", "mucho", "poco", "muy", "solo", "sólo",
    "tambien", "también", "pero", "porque", "cuando", "donde", "dónde",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _leer_aprendido() -> dict:
    try:
        if _RUTA_APRENDIDO.exists():
            datos = json.loads(_RUTA_APRENDIDO.read_text(encoding="utf-8"))
            return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def _escribir_aprendido(datos: dict) -> None:
    _RUTA_APRENDIDO.parent.mkdir(parents=True, exist_ok=True)
    _RUTA_APRENDIDO.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _invalidar_cache() -> None:
    global _dominios_cache
    _dominios_cache = None


def dominios() -> dict:
    """Base curada + conocimiento aprendido (sin mutar el JSON base)."""
    global _dominios_cache
    if _dominios_cache is not None:
        return _dominios_cache

    base = json.loads(_RUTA.read_text(encoding="utf-8"))
    aprendido = _leer_aprendido()

    for clave, extra in aprendido.items():
        if clave not in base:
            continue
        actual = base[clave]
        palabras = list(actual.get("palabras_clave", []))
        for palabra in extra.get("palabras_clave", []):
            if palabra not in palabras:
                palabras.append(palabra)
        actual["palabras_clave"] = palabras
        actual["ejemplos"] = list(extra.get("ejemplos", []))

    _dominios_cache = base
    return _dominios_cache


def _tokens(texto: str) -> set[str]:
    plano = _normalizar(texto)
    return {
        t for t in re.findall(r"[a-z0-9]+", plano)
        if len(t) >= 4 and t not in _VACIAS
    }


def _similitud(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def detectar_dominio(texto: str) -> str | None:
    """Palabra clave exacta o frase parecida a un ejemplo aprendido."""
    plano = _normalizar(texto)

    for clave, cfg in dominios().items():
        for palabra in cfg.get("palabras_clave", []):
            if _normalizar(palabra) in plano:
                return clave

    mejor_clave, mejor_puntaje = None, 0.0
    for clave, cfg in dominios().items():
        for ejemplo in cfg.get("ejemplos", []):
            puntaje = _similitud(texto, ejemplo)
            if puntaje > mejor_puntaje:
                mejor_clave, mejor_puntaje = clave, puntaje

    return mejor_clave if mejor_puntaje >= 0.6 else None


def aprender_ejemplo(dominio: str, frase: str) -> bool:
    """Guarda una frase real del usuario como ejemplo del dominio."""
    if dominio not in dominios():
        return False

    frase = (frase or "").strip()
    if len(frase) < 3:
        return False

    aprendido = _leer_aprendido()
    entrada = aprendido.setdefault(dominio, {"palabras_clave": [], "ejemplos": []})
    ejemplos = entrada.setdefault("ejemplos", [])

    normalizadas = {_normalizar(e) for e in ejemplos}
    if _normalizar(frase) not in normalizadas:
        ejemplos.append(frase)
        entrada["ejemplos"] = ejemplos[-50:]

    _escribir_aprendido(aprendido)
    _invalidar_cache()
    return True


def aprender_palabras(dominio: str, palabras: list[str]) -> bool:
    """Añade palabras clave manualmente al dominio."""
    if dominio not in dominios():
        return False

    aprendido = _leer_aprendido()
    entrada = aprendido.setdefault(dominio, {"palabras_clave": [], "ejemplos": []})
    claves = entrada.setdefault("palabras_clave", [])
    existentes = {_normalizar(p) for p in claves}

    agregado = False
    for palabra in palabras or []:
        palabra = (palabra or "").strip()
        if palabra and _normalizar(palabra) not in existentes:
            claves.append(palabra)
            existentes.add(_normalizar(palabra))
            agregado = True

    if agregado:
        _escribir_aprendido(aprendido)
        _invalidar_cache()
    return agregado


def listar_aprendido() -> dict:
    return _leer_aprendido()


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

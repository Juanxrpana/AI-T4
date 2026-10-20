"""Test del fallback entre modelos (sin llamar a la API real)."""

import asyncio

from ai import gemini as gemini_mod
from ai.gemini import ProveedorGemini


def _respuesta_derivar():
    return {
        "tipo_respuesta": "derivar",
        "mensaje": "ok",
        "especialidad_sugerida": None,
        "especialidades_disponibles": [],
        "pregunta_aclaratoria": "",
        "observacion": "",
        "accion_sugerida": {"etiqueta": "", "ruta": "", "visible": False},
    }


def test_fallback_si_el_primero_falla(monkeypatch):
    p = ProveedorGemini()
    p.modelos = ["modelo-malo", "modelo-bueno"]
    llamadas = []

    async def fake_con_modelo(modelo, consulta, historial):
        llamadas.append(modelo)
        if modelo == "modelo-malo":
            raise RuntimeError("503 UNAVAILABLE")
        return _respuesta_derivar()

    # Evita que orientar() llame a PHP para el catálogo.
    monkeypatch.setattr(
        gemini_mod.php_client,
        "get_catalogo_cache_sincrono",
        lambda: [{"nombre": "Cardiología"}],
    )
    monkeypatch.setattr(p, "_con_modelo", fake_con_modelo)

    res = asyncio.run(p.orientar("hola"))

    assert llamadas == ["modelo-malo", "modelo-bueno"]
    assert res["mensaje"] == "ok"


def test_lista_modelos_sin_duplicados(monkeypatch):
    p = ProveedorGemini()
    p.modelo = "gemini-x"
    monkeypatch.setattr(
        gemini_mod.settings,
        "MODELOS_FALLBACK",
        "gemini-x, gemini-y, gemini-y, ,gemini-z",
    )

    assert p._lista_modelos() == ["gemini-x", "gemini-y", "gemini-z"]


def test_accion_catalogo_va_a_especialidades():
    from ai.schemas import RespuestaOrientacion
    from config import RUTAS_FRONTEND

    p = ProveedorGemini()
    r = RespuestaOrientacion(
        tipo_respuesta="catalogo",
        mensaje="Estas son las especialidades.",
        especialidades_disponibles=["CONSULTA GENERAL"],
    )

    accion = p._construir_accion(r)

    assert accion["visible"] is True
    assert accion["ruta"] == RUTAS_FRONTEND["especialidades"]
    assert accion["ruta"].endswith("/Servicios/servicios")


def test_accion_navegacion_pacientes():
    from ai.schemas import RespuestaOrientacion
    from config import RUTAS_FRONTEND

    p = ProveedorGemini()
    r = RespuestaOrientacion(
        tipo_respuesta="navegacion",
        mensaje="Puede ver la lista en el módulo de Pacientes.",
        modulo_sugerido="pacientes",
    )

    accion = p._construir_accion(r)

    assert accion["visible"] is True
    assert accion["ruta"] == RUTAS_FRONTEND["pacientes"]
    assert accion["ruta"].endswith("/Pacientes/getPacientes")

"""Tests del registro de proveedores y del adaptador OpenAI-compatible."""

import asyncio
from types import SimpleNamespace

import pytest

from ai import proveedores as prov_mod
from ai.base import ProveedorIA
from ai.openai_compatible import (
    ConfigProveedor,
    ProveedorOpenAICompatible,
    _es_json,
    _resumen_content,
    _resumen_reasoning,
    esquema_tool,
    mensajes_openai,
)
from ai.proveedores import ProveedorFallback, construir, crear_proveedor
from tools.clinica import listar_doctores, mis_datos


class _Fake(ProveedorIA):
    def __init__(self, nombre, respuesta=None, error=None):
        self._nombre = nombre
        self._respuesta = respuesta
        self._error = error

    @property
    def nombre_modelo(self):
        return self._nombre

    async def orientar(self, consulta, historial=None):
        if self._error:
            raise self._error
        return self._respuesta


def _respuesta():
    return {"tipo_respuesta": "derivar", "mensaje": "ok"}


def test_esquema_tool_con_argumento():
    esquema = esquema_tool(listar_doctores)

    assert esquema["type"] == "function"
    assert esquema["function"]["name"] == "listar_doctores"
    assert esquema["function"]["parameters"]["properties"]["especialidad"]["type"] == "string"
    assert esquema["function"]["parameters"]["required"] == ["especialidad"]


def test_esquema_tool_sin_argumentos():
    esquema = esquema_tool(mis_datos)

    assert esquema["function"]["name"] == "mis_datos"
    assert esquema["function"]["parameters"]["required"] == []


def test_es_json_acepta_fences_y_rechaza_vacio():
    assert _es_json('{"tipo_respuesta": "derivar"}')
    assert _es_json('```json\n{"tipo_respuesta": "derivar"}\n```')
    assert not _es_json("")
    assert not _es_json("   ")
    assert not _es_json("texto plano")


def test_resumen_content_y_reasoning():
    assert _resumen_content(None)["tipo"] == "null"
    assert _resumen_content("   ")["blanco"] is True
    assert _resumen_content("hola")["len"] == 4
    assert _resumen_reasoning({"reasoning_content": "pensando"})[
        "reasoning_content"
    ]["len"] == 8


@pytest.mark.parametrize("contenido", ["", "   ", None])
def test_texto_vacio_no_se_usa(contenido):
    assert ProveedorOpenAICompatible._texto(SimpleNamespace(content=contenido)) == ""


def test_texto_rescata_json_de_reasoning():
    mensaje = SimpleNamespace(
        content="",
        model_extra={"reasoning_content": 'pienso... {"tipo_respuesta": "derivar"} fin'},
    )

    assert ProveedorOpenAICompatible._texto(mensaje) == '{"tipo_respuesta": "derivar"}'


def test_texto_usa_content_o_partes():
    assert ProveedorOpenAICompatible._texto(
        SimpleNamespace(content='{"tipo_respuesta": "derivar"}')
    ) == '{"tipo_respuesta": "derivar"}'
    assert ProveedorOpenAICompatible._texto(
        SimpleNamespace(content=[{"text": "hola"}])
    ) == "hola"


def test_mensajes_mapea_model_a_assistant():
    mensajes = mensajes_openai(
        "dolor de cabeza",
        [{"role": "user", "text": "hola"}, {"role": "model", "text": "respuesta"}],
        "guia de prueba",
    )

    assert mensajes[0]["role"] == "system"
    assert "guia de prueba" in mensajes[0]["content"]
    assert [m["role"] for m in mensajes] == ["system", "user", "assistant", "user"]
    assert mensajes[-1]["content"] == "dolor de cabeza"


def test_reintenta_cuando_el_modelo_devuelve_vacio(monkeypatch):
    proveedor = ProveedorOpenAICompatible(
        ConfigProveedor(
            nombre="custom",
            api_key="k",
            base_url="https://example.test/v1",
            modelo="m",
        )
    )
    respuestas = [
        SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="   "), finish_reason="stop"
        )]),
        SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=""), finish_reason="stop"
        )]),
        SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"tipo_respuesta": "derivar", "mensaje": "ok"}'),
            finish_reason="stop",
        )]),
    ]
    llamadas = []

    async def fake_crear(modelo, mensajes, usar_tools=True, usar_json=None):
        llamadas.append((usar_tools, usar_json))
        return respuestas.pop(0)

    monkeypatch.setattr(proveedor, "_crear", fake_crear)

    resultado = asyncio.run(proveedor._con_modelo("m", []))

    assert resultado["tipo_respuesta"] == "derivar"
    assert len(llamadas) == 3
    assert llamadas == [(True, None), (False, True), (False, True)]


def test_no_reintenta_si_el_primer_json_es_valido(monkeypatch):
    proveedor = ProveedorOpenAICompatible(
        ConfigProveedor(
            nombre="custom",
            api_key="k",
            base_url="https://example.test/v1",
            modelo="m",
        )
    )
    respuesta = SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content='{"tipo_respuesta": "derivar", "mensaje": "ok"}'),
        finish_reason="stop",
    )])
    llamadas = []

    async def fake_crear(modelo, mensajes, usar_tools=True, usar_json=None):
        llamadas.append((usar_tools, usar_json))
        return respuesta

    monkeypatch.setattr(proveedor, "_crear", fake_crear)

    resultado = asyncio.run(proveedor._con_modelo("m", []))

    assert resultado["tipo_respuesta"] == "derivar"
    assert llamadas == [(True, None)]


def test_fallback_usa_el_segundo_si_el_primero_falla():
    fallback = ProveedorFallback([
        _Fake("malo", error=RuntimeError("caído")),
        _Fake("bueno", respuesta=_respuesta()),
    ])

    resultado = asyncio.run(fallback.orientar("hola"))

    assert resultado["mensaje"] == "ok"
    assert fallback.nombre_modelo == "bueno"


def test_fallback_falla_si_todos_fallan():
    fallback = ProveedorFallback([_Fake("a", error=RuntimeError("x"))])

    with pytest.raises(RuntimeError):
        asyncio.run(fallback.orientar("hola"))


def test_crear_proveedor_principal_y_respaldo(monkeypatch):
    monkeypatch.setattr(prov_mod.settings, "PROVEEDOR_IA", "opencode")
    monkeypatch.setattr(prov_mod.settings, "PROVEEDORES_FALLBACK", "gemini")
    monkeypatch.setattr(prov_mod.settings, "OPENCODE_API_KEY", "oc_test")
    monkeypatch.setattr(prov_mod.settings, "OPENCODE_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(prov_mod.settings, "MODELO_OPENCODE", "modelo-test")

    proveedor = crear_proveedor()

    assert isinstance(proveedor, ProveedorFallback)
    assert isinstance(proveedor.proveedores[0], ProveedorOpenAICompatible)
    assert proveedor.proveedores[0].config.nombre == "opencode"
    assert proveedor.proveedores[0].config.headers.keys() == {"x-opencode-session"}


def test_respaldo_mal_configurado_no_rompe(monkeypatch):
    monkeypatch.setattr(prov_mod.settings, "PROVEEDOR_IA", "opencode")
    monkeypatch.setattr(prov_mod.settings, "PROVEEDORES_FALLBACK", "gemini")
    monkeypatch.setattr(prov_mod.settings, "OPENCODE_API_KEY", "oc_test")
    monkeypatch.setattr(prov_mod.settings, "OPENCODE_BASE_URL", "https://example.test/v1")
    monkeypatch.setattr(prov_mod.settings, "MODELO_OPENCODE", "modelo-test")

    construir_real = prov_mod.construir

    def construir_fake(nombre):
        if nombre == "gemini":
            raise ValueError("sin key")
        return construir_real(nombre)

    monkeypatch.setattr(prov_mod, "construir", construir_fake)

    proveedor = crear_proveedor()

    assert isinstance(proveedor, ProveedorOpenAICompatible)


def test_sin_proveedor_principal_falla(monkeypatch):
    monkeypatch.setattr(prov_mod.settings, "PROVEEDOR_IA", "")

    with pytest.raises(ValueError):
        crear_proveedor()


def test_proveedor_desconocido():
    with pytest.raises(ValueError):
        construir("inexistente")


def test_config_sin_api_key_falla():
    with pytest.raises(ValueError):
        ProveedorOpenAICompatible(
            ConfigProveedor(
                nombre="custom",
                api_key="",
                base_url="https://example.test/v1",
                modelo="x",
            )
        )

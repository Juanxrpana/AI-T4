"""Tests de la tool `listar_doctores` (se mockea el cliente HTTP hacia PHP)."""

import asyncio

import tools.clinica as clinica
import tools.php_client as php_client


def test_listar_doctores_especialidad_existente(monkeypatch):
    async def fake_catalogo(forzar_refresh=False):
        return [{"id_categoria": 5, "nombre": "Cardiología"}]

    async def fake_doctores(id_categoria):
        assert id_categoria == 5
        return [
            {"id_personal": 1, "nombre_doctor": "Ana", "apellido_doctor": "Pérez"},
            {"id_personal": 2, "nombre_doctor": "Luis", "apellido_doctor": "Gómez"},
        ]

    monkeypatch.setattr(php_client, "get_catalogo_especialidades", fake_catalogo)
    monkeypatch.setattr(php_client, "get_doctores_por_id_categoria", fake_doctores)

    # La comparación de nombres ignora mayúsculas y espacios.
    res = asyncio.run(clinica.listar_doctores("  cardiología  "))
    assert res == [
        {"id": 1, "nombre": "Ana Pérez"},
        {"id": 2, "nombre": "Luis Gómez"},
    ]


def test_listar_doctores_especialidad_inexistente(monkeypatch):
    async def fake_catalogo(forzar_refresh=False):
        return [{"id_categoria": 5, "nombre": "Cardiología"}]

    monkeypatch.setattr(php_client, "get_catalogo_especialidades", fake_catalogo)

    res = asyncio.run(clinica.listar_doctores("Traumatología"))
    assert res == []


def test_tools_incluye_mis_datos():
    nombres = {t.__name__ for t in clinica.TOOLS}
    assert {"listar_doctores", "mis_datos"} <= nombres


def test_mis_datos_sin_usuario(monkeypatch):
    token = php_client.usuario_actual.set(None)
    try:
        res = asyncio.run(clinica.mis_datos())
        assert res["ok"] is False
    finally:
        php_client.usuario_actual.reset(token)


def test_mis_datos_con_usuario(monkeypatch):
    async def fake_get_mis_datos(id_usuario):
        assert id_usuario == 7
        return {"ok": True, "acceso": "permitido", "paciente": {"id_paciente": 1}}

    monkeypatch.setattr(php_client, "get_mis_datos", fake_get_mis_datos)

    token = php_client.usuario_actual.set("7")
    try:
        res = asyncio.run(clinica.mis_datos())
        assert res["acceso"] == "permitido"
        assert res["paciente"]["id_paciente"] == 1
    finally:
        php_client.usuario_actual.reset(token)

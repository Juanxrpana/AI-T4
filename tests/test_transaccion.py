"""Fase 2: unidad de trabajo y outbox de auditoría."""

import sqlite3

from fastapi.testclient import TestClient

import main
from storage import auditoria, db

API_KEY = "test-api-key"


def _cliente(monkeypatch, orientar=None):
    async def _precargar():
        return None

    async def _orientar(consulta, historial=None):
        if orientar is not None:
            return orientar(consulta, historial)
        return {
            "tipo_respuesta": "orientacion",
            "mensaje": "Le sugiero Cardiología.",
            "especialidad_sugerida": "Cardiología",
            "especialidades_disponibles": [],
            "pregunta_aclaratoria": "",
            "observacion": "",
            "accion_sugerida": {"etiqueta": "Ver", "ruta": "/", "visible": True},
        }

    monkeypatch.setattr(main.proveedor, "precargar_catalogo", _precargar)
    monkeypatch.setattr(main.proveedor, "orientar", _orientar)
    return TestClient(main.app)


def _con():
    con = sqlite3.connect(str(db.DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def test_fallo_durable_devuelve_503_sin_evidencia(monkeypatch):
    async def _falla(*args, **kwargs):
        raise RuntimeError("fallo simulado de evidencia")

    monkeypatch.setattr(main.evidencia, "guardar_evidencia", _falla)

    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={
                "consulta": "necesito informacion general sobre una cita",
                "session_id": "tx-503",
                "peticion_id": "pet-tx-503",
            },
            headers={"X-API-Key": API_KEY},
        )

    assert r.status_code == 503

    con = _con()
    try:
        turno = con.execute(
            "SELECT id, respuesta_json FROM turno WHERE peticion_id = 'pet-tx-503'"
        ).fetchone()
        assert turno is not None
        assert turno["respuesta_json"] is None
        assert (
            con.execute(
                "SELECT COUNT(*) FROM evidencia_turno WHERE turno_id = ?",
                (turno["id"],),
            ).fetchone()[0]
            == 0
        )
        assert (
            con.execute(
                "SELECT COUNT(*) FROM auditoria_outbox WHERE idempotency_key = ?",
                (f"turno:{turno['id']}",),
            ).fetchone()[0]
            == 0
        )
        assert (
            con.execute(
                "SELECT COUNT(*) FROM mensajes WHERE session_id = 'tx-503' "
                "AND rol = 'model'"
            ).fetchone()[0]
            == 0
        )
    finally:
        con.close()


def test_turno_exitoso_deja_evidencia_y_auditoria(monkeypatch):
    with _cliente(monkeypatch) as c:
        r = c.post(
            "/orientar",
            json={
                "consulta": "necesito informacion general sobre una cita",
                "session_id": "tx-ok",
                "peticion_id": "pet-tx-ok",
            },
            headers={"X-API-Key": API_KEY},
        )

    assert r.status_code == 200
    turno_id = r.json()["turno_id"]

    con = _con()
    try:
        evidencia = con.execute(
            "SELECT * FROM evidencia_turno WHERE turno_id = ?", (turno_id,)
        ).fetchone()
        assert evidencia is not None
        assert evidencia["respuesta_final"]
        assert (
            con.execute(
                "SELECT COUNT(*) FROM evidencia_componente WHERE evidencia_id = ?",
                (evidencia["id"],),
            ).fetchone()[0]
            == 6
        )
        outbox = con.execute(
            "SELECT enviado_en FROM auditoria_outbox WHERE idempotency_key = ?",
            (f"turno:{turno_id}",),
        ).fetchone()
        assert outbox is not None and outbox["enviado_en"] is not None
        assert (
            con.execute(
                "SELECT COUNT(*) FROM auditoria WHERE idempotency_key = ?",
                (f"turno:{turno_id}",),
            ).fetchone()[0]
            == 1
        )
    finally:
        con.close()


def test_relay_es_idempotente_y_respeta_payload_invalido():
    con = _con()
    try:
        con.execute(
            "INSERT OR IGNORE INTO auditoria_outbox "
            "(idempotency_key, payload_json, creado_en) VALUES (?, ?, datetime('now'))",
            ("relay-test-1", '{"session_id": "relay", "consulta": "hola"}'),
        )
        con.execute(
            "INSERT OR IGNORE INTO auditoria_outbox "
            "(idempotency_key, payload_json, creado_en) VALUES (?, ?, datetime('now'))",
            ("relay-test-bad", "{no-es-json"),
        )
        con.commit()
    finally:
        con.close()

    import asyncio

    assert asyncio.run(auditoria.relay_auditoria()) >= 1
    # El segundo pase no duplica la auditoría válida.
    asyncio.run(auditoria.relay_auditoria())

    con = _con()
    try:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM auditoria WHERE idempotency_key = 'relay-test-1'"
            ).fetchone()[0]
            == 1
        )
        malo = con.execute(
            "SELECT enviado_en FROM auditoria_outbox WHERE idempotency_key = 'relay-test-bad'"
        ).fetchone()
        assert malo is not None and malo["enviado_en"] is None
    finally:
        con.close()

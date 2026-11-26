"""Fase 4: normalización operativa aditiva y backfill."""

import asyncio
import sqlite3

import pytest

from storage import auditoria, db, memoria, normalizacion, sesiones


def test_estado_sesion_se_normaliza_y_actualiza():
    async def flujo():
        sid = "norm-estado"
        await sesiones.crear_sesion(
            sid, "u-norm", {"dominio": "fiebre", "respuestas": {"a": "1"}}
        )
        assert await normalizacion.leer_estado(sid) == {
            "dominio": "fiebre",
            "respuestas": {"a": "1"},
        }

        await sesiones.guardar_estado(
            sid, {"dominio": "fiebre", "respuestas": {"a": "2"}}
        )
        assert await normalizacion.leer_estado(sid) == {
            "dominio": "fiebre",
            "respuestas": {"a": "2"},
        }

        sesion = await sesiones.obtener_sesion(sid)
        assert sesion["estado"] == {
            "dominio": "fiebre",
            "respuestas": {"a": "2"},
        }

    asyncio.run(flujo())


def test_memoria_normaliza_datos_y_embedding():
    async def flujo():
        await memoria.guardar(
            "u-norm", "p-norm", "resumen",
            {"alergias": ["penicilina"], "edad": 30},
        )

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT id FROM memorias WHERE id_usuario = ? AND id_paciente = ?",
                ("u-norm", "p-norm"),
            ) as cur:
                fila = await cur.fetchone()
        finally:
            await con.close()

        memoria_id = int(fila["id"])
        assert await normalizacion.leer_datos_memoria(memoria_id) == {
            "alergias": ["penicilina"],
            "edad": 30,
        }

        await memoria.actualizar_embedding(
            "u-norm", "p-norm", [0.1, 0.2, 0.3]
        )
        embedding = await normalizacion.leer_embedding(memoria_id)
        assert embedding == pytest.approx([0.1, 0.2, 0.3])

    asyncio.run(flujo())


def test_auditoria_normaliza_respuesta():
    async def flujo():
        await auditoria.registrar({
            "session_id": "norm-aud",
            "json_respuesta": {"tipo_respuesta": "orientacion", "ok": True},
            "resultado": "ok",
        })

        con = await db.conectar()
        try:
            async with con.execute(
                "SELECT id FROM auditoria WHERE session_id = 'norm-aud' "
                "ORDER BY id DESC LIMIT 1"
            ) as cur:
                fila = await cur.fetchone()
        finally:
            await con.close()

        assert await normalizacion.leer_respuesta(int(fila["id"])) == {
            "ok": True,
            "tipo_respuesta": "orientacion",
        }

    asyncio.run(flujo())


def test_backfill_de_datos_legacy(tmp_path, monkeypatch):
    ruta = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "DB_PATH", ruta)

    con = sqlite3.connect(str(ruta))
    try:
        con.executescript(db.SCHEMA)
        con.execute(
            "INSERT INTO sesiones "
            "(session_id, id_usuario, estado_json, creada_en, actualizada_en) "
            "VALUES ('legacy-s', 'u', '{\"dominio\":\"fiebre\"}', '2026-01-01', '2026-01-01')"
        )
        con.execute(
            "INSERT INTO memorias "
            "(id_usuario, id_paciente, resumen, datos_json, embedding, actualizada_en) "
            "VALUES ('u', 'p', 'r', '{\"edad\":30}', '[0.5,0.25]', '2026-01-01')"
        )
        con.execute(
            "INSERT INTO auditoria (ts, session_id, json_respuesta) "
            "VALUES ('2026-01-01', 'legacy-s', '{\"tipo_respuesta\":\"orientacion\"}')"
        )
        con.commit()
    finally:
        con.close()

    asyncio.run(db.init_db())

    con = sqlite3.connect(str(ruta))
    con.row_factory = sqlite3.Row
    try:
        estado = {
            fila["clave"]: fila["valor_json"]
            for fila in con.execute(
                "SELECT clave, valor_json FROM sesion_estado "
                "WHERE session_id = 'legacy-s'"
            )
        }
        assert estado == {"dominio": '"fiebre"'}

        assert con.execute(
            "SELECT COUNT(*) FROM memoria_dato WHERE memoria_id = 1"
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM memoria_embedding WHERE memoria_id = 1"
        ).fetchone()[0] == 2
        assert con.execute(
            "SELECT COUNT(*) FROM auditoria_respuesta WHERE auditoria_id = 1"
        ).fetchone()[0] == 1
    finally:
        con.close()

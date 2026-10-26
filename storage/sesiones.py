"""Repositorio de sesiones y mensajes (SQLite)."""

import json
from datetime import datetime, timezone

import aiosqlite

from storage.db import DB_PATH


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


async def obtener_sesion(session_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT session_id, id_usuario, estado_json FROM sesiones WHERE session_id = ?",
            (session_id,),
        ) as cur:
            fila = await cur.fetchone()

    if not fila:
        return None

    try:
        estado = json.loads(fila["estado_json"] or "{}")
    except (TypeError, ValueError):
        estado = {}

    return {
        "session_id": fila["session_id"],
        "id_usuario": fila["id_usuario"],
        "estado": estado,
    }


async def crear_sesion(session_id: str, id_usuario: str | None, estado: dict | None = None) -> dict:
    ahora = _ahora()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sesiones (session_id, id_usuario, estado_json, creada_en, actualizada_en) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "id_usuario = COALESCE(excluded.id_usuario, sesiones.id_usuario), "
            "actualizada_en = excluded.actualizada_en",
            (
                session_id,
                id_usuario,
                json.dumps(estado or {}, ensure_ascii=False),
                ahora,
                ahora,
            ),
        )
        await db.commit()

    return await obtener_sesion(session_id)


async def guardar_estado(session_id: str, estado: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sesiones SET estado_json = ?, actualizada_en = ? WHERE session_id = ?",
            (json.dumps(estado, ensure_ascii=False), _ahora(), session_id),
        )
        await db.commit()


async def agregar_mensaje(session_id: str, rol: str, texto: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO mensajes (session_id, ts, rol, texto) VALUES (?, ?, ?, ?)",
            (session_id, _ahora(), rol, texto),
        )
        await db.commit()


async def listar_mensajes(session_id: str, limite: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT ts, rol, texto FROM mensajes WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limite),
        ) as cur:
            filas = await cur.fetchall()

    return [dict(f) for f in reversed(filas)]


async def historial_para_gemini(session_id: str, limite: int = 12) -> list[dict]:
    """Últimos mensajes en el formato que espera Gemini (role/text)."""
    filas = await listar_mensajes(session_id, limite)
    return [{"role": f["rol"], "text": f["texto"]} for f in filas]


async def borrar_sesion(session_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM mensajes WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sesiones WHERE session_id = ?", (session_id,))
        await db.commit()

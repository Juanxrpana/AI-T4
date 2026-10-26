"""Memoria por usuario + paciente (resúmenes en SQLite).

Guarda un resumen de los datos clínicos vistos para no reconsultar a PHP en
cada mensaje del mismo paciente. El alcance es por usuario, etiquetado por
paciente, para no mezclar historiales.
"""

import json
from datetime import datetime, timezone

import aiosqlite

from storage.db import DB_PATH


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


async def guardar(
    id_usuario: str,
    id_paciente: str | int | None,
    resumen: str,
    datos: dict | None = None,
) -> None:
    clave_paciente = "" if id_paciente in (None, "") else str(id_paciente)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memorias (id_usuario, id_paciente, resumen, datos_json, actualizada_en) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(id_usuario, id_paciente) DO UPDATE SET "
            "resumen = excluded.resumen, datos_json = excluded.datos_json, "
            "actualizada_en = excluded.actualizada_en",
            (
                str(id_usuario),
                clave_paciente,
                resumen,
                json.dumps(datos or {}, ensure_ascii=False),
                _ahora(),
            ),
        )
        await db.commit()


async def obtener(id_usuario: str, id_paciente: str | int | None) -> dict | None:
    clave_paciente = "" if id_paciente in (None, "") else str(id_paciente)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id_usuario, id_paciente, resumen, datos_json, actualizada_en "
            "FROM memorias WHERE id_usuario = ? AND id_paciente = ?",
            (str(id_usuario), clave_paciente),
        ) as cur:
            fila = await cur.fetchone()

    if not fila:
        return None

    try:
        datos = json.loads(fila["datos_json"] or "{}")
    except (TypeError, ValueError):
        datos = {}

    return {
        "id_usuario": fila["id_usuario"],
        "id_paciente": fila["id_paciente"],
        "resumen": fila["resumen"],
        "datos": datos,
        "actualizada_en": fila["actualizada_en"],
    }


async def borrar(id_usuario: str, id_paciente: str | int | None = None) -> None:
    """Borra la memoria de un paciente o, si no se indica, toda la del usuario."""
    async with aiosqlite.connect(DB_PATH) as db:
        if id_paciente is None:
            await db.execute("DELETE FROM memorias WHERE id_usuario = ?", (str(id_usuario),))
        else:
            clave = "" if id_paciente == "" else str(id_paciente)
            await db.execute(
                "DELETE FROM memorias WHERE id_usuario = ? AND id_paciente = ?",
                (str(id_usuario), clave),
            )
        await db.commit()

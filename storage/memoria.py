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
            "SELECT id_usuario, id_paciente, resumen, datos_json, embedding, actualizada_en "
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

    try:
        embedding = json.loads(fila["embedding"]) if fila["embedding"] else None
    except (TypeError, ValueError):
        embedding = None

    return {
        "id_usuario": fila["id_usuario"],
        "id_paciente": fila["id_paciente"],
        "resumen": fila["resumen"],
        "datos": datos,
        "embedding": embedding,
        "actualizada_en": fila["actualizada_en"],
    }


async def actualizar_embedding(
    id_usuario: str, id_paciente: str | int | None, embedding: list[float] | None
) -> None:
    if not embedding:
        return

    clave_paciente = "" if id_paciente in (None, "") else str(id_paciente)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE memorias SET embedding = ? WHERE id_usuario = ? AND id_paciente = ?",
            (json.dumps(embedding), str(id_usuario), clave_paciente),
        )
        await db.commit()


def _coseno(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = sum(x * x for x in a) ** 0.5
    norma_b = sum(y * y for y in b) ** 0.5
    if not norma_a or not norma_b:
        return 0.0
    return producto / (norma_a * norma_b)


async def buscar_similares(id_usuario: str, vector: list[float], k: int = 5) -> list[dict]:
    """Ranking por similitud coseno de las memorias del usuario."""
    if not vector:
        return []

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id_paciente, resumen, embedding FROM memorias "
            "WHERE id_usuario = ? AND embedding IS NOT NULL",
            (str(id_usuario),),
        ) as cur:
            filas = await cur.fetchall()

    resultados = []
    for fila in filas:
        try:
            emb = json.loads(fila["embedding"])
        except (TypeError, ValueError):
            continue
        resultados.append({
            "id_paciente": fila["id_paciente"],
            "resumen": fila["resumen"],
            "score": round(_coseno(vector, emb), 4),
        })

    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados[: max(1, int(k))]


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

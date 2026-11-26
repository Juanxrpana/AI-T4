"""Lectura de las tablas operativas normalizadas (Fase 4).

Las columnas JSON siguen siendo el contrato del runtime; estas funciones
permiten comparar y consumir la representación normalizada sin cambiar la
respuesta actual.
"""

import json

from storage import db as db_mod


def _json(valor: str):
    try:
        return json.loads(valor)
    except (TypeError, ValueError):
        return None


async def leer_estado(session_id: str) -> dict:
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT clave, valor_json FROM sesion_estado WHERE session_id = ? "
            "ORDER BY clave",
            (session_id,),
        ) as cur:
            filas = await cur.fetchall()
    finally:
        await con.close()
    return {fila["clave"]: _json(fila["valor_json"]) for fila in filas}


async def leer_datos_memoria(memoria_id: int) -> dict:
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT clave, valor_json FROM memoria_dato WHERE memoria_id = ? "
            "ORDER BY clave",
            (memoria_id,),
        ) as cur:
            filas = await cur.fetchall()
    finally:
        await con.close()
    return {fila["clave"]: _json(fila["valor_json"]) for fila in filas}


async def leer_embedding(memoria_id: int) -> list[float]:
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT valor FROM memoria_embedding WHERE memoria_id = ? "
            "ORDER BY indice",
            (memoria_id,),
        ) as cur:
            filas = await cur.fetchall()
    finally:
        await con.close()
    return [float(fila["valor"]) for fila in filas]


async def leer_respuesta(auditoria_id: int) -> dict:
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT clave, valor_json FROM auditoria_respuesta "
            "WHERE auditoria_id = ? ORDER BY clave",
            (auditoria_id,),
        ) as cur:
            filas = await cur.fetchall()
    finally:
        await con.close()
    return {fila["clave"]: _json(fila["valor_json"]) for fila in filas}

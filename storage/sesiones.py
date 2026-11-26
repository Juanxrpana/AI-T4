"""Repositorio de sesiones, consultas, turnos y mensajes (SQLite)."""

import json
from datetime import datetime, timezone

import aiosqlite

from storage import db as db_mod


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fila(fila: aiosqlite.Row | None) -> dict | None:
    return dict(fila) if fila is not None else None


async def _escribir(db, sql: str, params, retornar_id: bool = False):
    """Escribe con la conexión de la unidad de trabajo o con una propia."""
    if db is None:
        con = await db_mod.conectar()
        try:
            cur = await con.execute(sql, params)
            await con.commit()
            return int(cur.lastrowid) if retornar_id else None
        finally:
            await con.close()

    cur = await db.execute(sql, params)
    return int(cur.lastrowid) if retornar_id else None


class PeticionIdConflicto(Exception):
    """El `peticion_id` ya pertenece a otra consulta."""


def _turno_existente(consulta_id: int, fila: aiosqlite.Row) -> dict:
    if fila["consulta_id"] != consulta_id:
        raise PeticionIdConflicto(
            f"peticion_id {fila['peticion_id']} pertenece a otra consulta"
        )
    return dict(fila)


async def obtener_sesion(session_id: str) -> dict | None:
    db = await db_mod.conectar()
    try:
        async with db.execute(
            "SELECT session_id, id_usuario, estado_json FROM sesiones "
            "WHERE session_id = ?",
            (session_id,),
        ) as cur:
            fila = await cur.fetchone()
    finally:
        await db.close()

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


async def crear_sesion(
    session_id: str, id_usuario: str | None, estado: dict | None = None
) -> dict:
    ahora = _ahora()
    db = await db_mod.conectar()
    try:
        await db.execute(
            "INSERT INTO sesiones "
            "(session_id, id_usuario, estado_json, creada_en, actualizada_en) "
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
    finally:
        await db.close()

    return await obtener_sesion(session_id)


async def guardar_estado(session_id: str, estado: dict, db=None) -> None:
    await _escribir(
        db,
        "UPDATE sesiones SET estado_json = ?, actualizada_en = ? "
        "WHERE session_id = ?",
        (json.dumps(estado, ensure_ascii=False), _ahora(), session_id),
    )


async def agregar_mensaje(
    session_id: str,
    rol: str,
    texto: str,
    consulta_id: int | None = None,
    turno_id: int | None = None,
    db=None,
) -> int:
    return await _escribir(
        db,
        "INSERT INTO mensajes "
        "(session_id, ts, rol, texto, consulta_id, turno_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, _ahora(), rol, texto, consulta_id, turno_id),
        retornar_id=True,
    )


async def listar_mensajes(session_id: str, limite: int = 50) -> list[dict]:
    db = await db_mod.conectar()
    try:
        async with db.execute(
            "SELECT ts, rol, texto FROM mensajes WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limite),
        ) as cur:
            filas = await cur.fetchall()
    finally:
        await db.close()

    return [dict(f) for f in reversed(filas)]


async def historial_para_gemini(session_id: str, limite: int = 12) -> list[dict]:
    """Últimos mensajes en el formato que espera Gemini (role/text)."""
    filas = await listar_mensajes(session_id, limite)
    return [{"role": f["rol"], "text": f["texto"]} for f in filas]


# ---------------------------------------------------------------------------
# Identidad consulta / turno
# ---------------------------------------------------------------------------


async def obtener_o_crear_consulta(
    session_id: str, id_usuario: str | None
) -> dict:
    """Devuelve la consulta abierta de la sesión o crea una nueva.

    No crea turnos: eso lo hace `crear_turno()` para que cada petición tenga
    exactamente un turno.
    """
    db = await db_mod.conectar()
    try:
        async with db.execute(
            "SELECT * FROM consulta WHERE session_id = ? AND estado = 'abierta'",
            (session_id,),
        ) as cur:
            fila = await cur.fetchone()
        if fila:
            return dict(fila)

        try:
            cur = await db.execute(
                "INSERT INTO consulta "
                "(session_id, id_usuario, flujo, estado, creada_en) "
                "VALUES (?, ?, 'general', 'abierta', ?)",
                (session_id, id_usuario, _ahora()),
            )
            await db.commit()
            consulta_id = int(cur.lastrowid)
        except aiosqlite.IntegrityError:
            # Otra petición creó la consulta abierta entre el SELECT y el INSERT.
            await db.rollback()
            async with db.execute(
                "SELECT * FROM consulta WHERE session_id = ? AND estado = 'abierta'",
                (session_id,),
            ) as cur:
                fila = await cur.fetchone()
            if not fila:
                raise
            return dict(fila)

        async with db.execute(
            "SELECT * FROM consulta WHERE id = ?", (consulta_id,)
        ) as cur:
            return dict(await cur.fetchone())
    finally:
        await db.close()


async def obtener_turno_por_peticion(peticion_id: str) -> dict | None:
    db = await db_mod.conectar()
    try:
        async with db.execute(
            "SELECT t.*, c.session_id AS consulta_session_id "
            "FROM turno t JOIN consulta c ON c.id = t.consulta_id "
            "WHERE t.peticion_id = ?",
            (peticion_id,),
        ) as cur:
            fila = await cur.fetchone()
        return dict(fila) if fila else None
    finally:
        await db.close()


async def crear_turno(
    consulta_id: int,
    peticion_id: str,
    texto: str = "",
    rol: str = "user",
) -> dict:
    """Crea el siguiente turno de la consulta o devuelve el ya existente.

    `peticion_id` es la clave de idempotencia del cliente.
    """
    db = await db_mod.conectar()
    try:
        async with db.execute(
            "SELECT * FROM turno WHERE peticion_id = ?", (peticion_id,)
        ) as cur:
            existente = await cur.fetchone()
        if existente:
            return _turno_existente(consulta_id, existente)

        for intento in range(3):
            async with db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM turno WHERE consulta_id = ?",
                (consulta_id,),
            ) as cur:
                seq = (await cur.fetchone())[0]

            try:
                cur = await db.execute(
                    "INSERT INTO turno "
                    "(consulta_id, seq, peticion_id, rol, texto, creado_en) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (consulta_id, seq, peticion_id, rol, texto, _ahora()),
                )
                await db.commit()
                turno_id = int(cur.lastrowid)
                break
            except aiosqlite.IntegrityError:
                await db.rollback()
                async with db.execute(
                    "SELECT * FROM turno WHERE peticion_id = ?", (peticion_id,)
                ) as cur:
                    existente = await cur.fetchone()
                if existente:
                    return _turno_existente(consulta_id, existente)
                if intento == 2:
                    raise
        else:
            raise RuntimeError("No se pudo asignar un turno")

        async with db.execute(
            "SELECT * FROM turno WHERE id = ?", (turno_id,)
        ) as cur:
            return dict(await cur.fetchone())
    finally:
        await db.close()


async def actualizar_turno(
    turno_id: int,
    tipo_respuesta: str | None = None,
    origen_respuesta: str | None = None,
    degradado: bool | None = None,
    respuesta_json: dict | None = None,
    db=None,
) -> None:
    campos: list[str] = []
    valores: list = []
    if tipo_respuesta is not None:
        campos.append("tipo_respuesta = ?")
        valores.append(tipo_respuesta)
    if origen_respuesta is not None:
        campos.append("origen_respuesta = ?")
        valores.append(origen_respuesta)
    if degradado is not None:
        campos.append("degradado = ?")
        valores.append(1 if degradado else 0)
    if respuesta_json is not None:
        campos.append("respuesta_json = ?")
        valores.append(json.dumps(respuesta_json, ensure_ascii=False))
    if not campos:
        return

    await _escribir(
        db,
        f"UPDATE turno SET {', '.join(campos)} WHERE id = ?",
        (*valores, turno_id),
    )


async def actualizar_consulta(
    consulta_id: int,
    flujo: str | None = None,
    dominio_id: int | None = None,
    id_paciente: str | None = None,
    db=None,
) -> None:
    campos: list[str] = []
    valores: list = []
    if flujo is not None:
        campos.append("flujo = ?")
        valores.append(flujo)
    if dominio_id is not None:
        campos.append("dominio_id = ?")
        valores.append(dominio_id)
    if id_paciente is not None:
        campos.append("id_paciente = ?")
        valores.append(id_paciente)
    if not campos:
        return

    await _escribir(
        db,
        f"UPDATE consulta SET {', '.join(campos)} WHERE id = ?",
        (*valores, consulta_id),
    )


async def cerrar_consulta(consulta_id: int, motivo: str, db=None) -> None:
    await _escribir(
        db,
        "UPDATE consulta SET estado = 'cerrada', motivo_cierre = ?, "
        "cerrada_en = ? WHERE id = ? AND estado = 'abierta'",
        (motivo, _ahora(), consulta_id),
    )


async def borrar_sesion(session_id: str) -> None:
    """Borra mensajes y sesión; la consulta conserva el caso con FK SET NULL."""
    db = await db_mod.conectar()
    try:
        await db.execute("DELETE FROM mensajes WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sesiones WHERE session_id = ?", (session_id,))
        await db.commit()
    finally:
        await db.close()

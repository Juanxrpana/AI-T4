"""Propuestas de conocimiento: creación, aprobación y rechazo.

Aprobar una propuesta escribe en la tabla del tipo correspondiente y publica
una nueva `kb_version` con el snapshot resultante. Nunca se autoaprueba.
"""

import logging
from datetime import datetime, timezone

from ai.evidencia import normalizar
from storage import conocimiento
from storage.db import unidad_de_trabajo

logger = logging.getLogger("asistente.propuestas")

TIPOS = {"palabra", "senal", "pregunta", "ejemplo"}


class PropuestaNoEncontrada(Exception):
    pass


class ConflictoPropuesta(Exception):
    pass


class Autoaprobacion(Exception):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _una(db, propuesta_id: int) -> dict | None:
    async with db.execute(
        "SELECT * FROM propuesta_conocimiento WHERE id = ?", (propuesta_id,)
    ) as cur:
        fila = await cur.fetchone()
    return dict(fila) if fila else None


async def crear(
    *,
    dominio_clave: str,
    tipo: str,
    valor: str,
    clave: str | None = None,
    capa_error: str = "conocimiento",
    generado_por: str | None = None,
    consulta_id: int | None = None,
    evidencia_turno_id: int | None = None,
    validacion_id: int | None = None,
    db=None,
) -> int | None:
    if tipo not in TIPOS:
        raise ConflictoPropuesta(f"tipo de propuesta inválido: {tipo}")
    valor = (valor or "").strip()
    if not valor:
        return None

    dominio_id = conocimiento.id_dominio(dominio_clave)
    if dominio_id is None:
        raise ConflictoPropuesta(f"dominio inexistente: {dominio_clave}")

    async def _insertar(con) -> int | None:
        cur = await con.execute(
            "INSERT OR IGNORE INTO propuesta_conocimiento "
            "(consulta_id, evidencia_turno_id, validacion_id, dominio_clave, "
            " dominio_id, tipo, clave, valor, valor_normalizado, capa_error, "
            " estado, generado_por, creada_en) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)",
            (
                consulta_id, evidencia_turno_id, validacion_id, dominio_clave,
                dominio_id, tipo, clave, valor, normalizar(valor), capa_error,
                generado_por, _ahora(),
            ),
        )
        if cur.rowcount == 0:
            return None
        return int(cur.lastrowid)

    if db is not None:
        return await _insertar(db)

    async with unidad_de_trabajo() as con:
        return await _insertar(con)


async def listar(
    *, estado: str | None = None, dominio: str | None = None,
    limite: int = 50,
) -> list[dict]:
    sql = "SELECT * FROM propuesta_conocimiento WHERE 1 = 1"
    params: list = []
    if estado:
        sql += " AND estado = ?"
        params.append(estado)
    if dominio:
        sql += " AND dominio_clave = ?"
        params.append(dominio)
    sql += " ORDER BY creada_en DESC, id DESC LIMIT ?"
    params.append(max(1, min(int(limite), 200)))

    con = await _conectar()
    try:
        async with con.execute(sql, params) as cur:
            filas = await cur.fetchall()
        return [dict(f) for f in filas]
    finally:
        await con.close()


async def aprobar(propuesta_id: int, actor_id: str) -> dict:
    async with unidad_de_trabajo() as db:
        propuesta = await _una(db, propuesta_id)
        if not propuesta:
            raise PropuestaNoEncontrada("propuesta no encontrada")
        if propuesta["estado"] != "pendiente":
            raise ConflictoPropuesta("la propuesta ya fue resuelta")
        if propuesta["generado_por"] and propuesta["generado_por"] == actor_id:
            raise Autoaprobacion("no puedes aprobar tu propia propuesta")

        dominio_id = propuesta["dominio_id"] or conocimiento.id_dominio(
            propuesta["dominio_clave"]
        )
        if dominio_id is None:
            raise ConflictoPropuesta("el dominio ya no existe")

        await _aplicar(db, propuesta, dominio_id)

        ahora = _ahora()
        await db.execute(
            "UPDATE propuesta_conocimiento SET estado = 'aprobada', "
            "aprobado_por = ?, resuelta_en = ? WHERE id = ?",
            (actor_id, ahora, propuesta_id),
        )
        propuesta = await _una(db, propuesta_id)

    try:
        await conocimiento.publicar_version(
            f"Propuesta {propuesta_id} aprobada por {actor_id}", actor_id
        )
    except Exception:
        logger.exception(
            "La propuesta %s se aplicó, pero no se pudo publicar versión",
            propuesta_id,
        )

    return propuesta


async def rechazar(propuesta_id: int, actor_id: str, motivo: str) -> dict:
    motivo = (motivo or "").strip()
    if not motivo:
        raise ConflictoPropuesta("el motivo de rechazo es obligatorio")

    async with unidad_de_trabajo() as db:
        propuesta = await _una(db, propuesta_id)
        if not propuesta:
            raise PropuestaNoEncontrada("propuesta no encontrada")
        if propuesta["estado"] != "pendiente":
            raise ConflictoPropuesta("la propuesta ya fue resuelta")

        await db.execute(
            "UPDATE propuesta_conocimiento SET estado = 'rechazada', "
            "aprobado_por = ?, motivo_rechazo = ?, resuelta_en = ? WHERE id = ?",
            (actor_id, motivo, _ahora(), propuesta_id),
        )
        return await _una(db, propuesta_id)


async def _aplicar(db, propuesta: dict, dominio_id: int) -> None:
    tipo = propuesta["tipo"]
    valor = propuesta["valor"]
    norm = propuesta["valor_normalizado"]
    ahora = _ahora()

    if tipo in {"palabra", "senal"}:
        tabla = (
            "dominio_palabra_clave" if tipo == "palabra"
            else "dominio_senal_alarma"
        )
        async with db.execute(
            f"SELECT id, alias_de FROM {tabla} "
            "WHERE dominio_id = ? AND valor_normalizado = ? "
            "ORDER BY alias_de IS NULL DESC LIMIT 1",
            (dominio_id, norm),
        ) as cur:
            existente = await cur.fetchone()

        if existente and existente["alias_de"] is None:
            await db.execute(
                f"UPDATE {tabla} SET origen = 'propuesta', activo = 1, "
                "estado = 'aprobado' WHERE id = ?",
                (existente["id"],),
            )
        else:
            await db.execute(
                f"INSERT INTO {tabla} "
                "(dominio_id, valor, valor_normalizado, origen, activo, "
                " estado, alias_de, creado_en) "
                "VALUES (?, ?, ?, 'propuesta', 1, 'aprobado', NULL, ?)",
                (dominio_id, valor, norm, ahora),
            )

    elif tipo == "ejemplo":
        await db.execute(
            "INSERT INTO dominio_ejemplo "
            "(dominio_id, texto, texto_normalizado, origen, creado_por, "
            " activo, estado, creado_en) "
            "VALUES (?, ?, ?, 'propuesta', ?, 1, 'aprobado', ?) "
            "ON CONFLICT(dominio_id, texto_normalizado) DO UPDATE SET "
            "origen = 'propuesta', activo = 1, estado = 'aprobado'",
            (dominio_id, valor, norm, propuesta["generado_por"], ahora),
        )

    elif tipo == "pregunta":
        clave = (propuesta["clave"] or "").strip()
        if not clave:
            raise ConflictoPropuesta("la propuesta de pregunta requiere clave")
        async with db.execute(
            "SELECT id FROM dominio_pregunta WHERE dominio_id = ? AND clave = ?",
            (dominio_id, clave),
        ) as cur:
            existente = await cur.fetchone()
        if existente:
            await db.execute(
                "UPDATE dominio_pregunta SET texto = ?, activo = 1, "
                "estado = 'aprobado' WHERE id = ?",
                (valor, existente["id"]),
            )
        else:
            async with db.execute(
                "SELECT COALESCE(MAX(orden), 0) + 1 FROM dominio_pregunta "
                "WHERE dominio_id = ?",
                (dominio_id,),
            ) as cur:
                orden = (await cur.fetchone())[0]
            await db.execute(
                "INSERT INTO dominio_pregunta "
                "(dominio_id, clave, texto, orden, activo, estado, creado_en) "
                "VALUES (?, ?, ?, ?, 1, 'aprobado', ?)",
                (dominio_id, clave, valor, orden, ahora),
            )


async def _conectar():
    from storage import db as db_mod

    return await db_mod.conectar()

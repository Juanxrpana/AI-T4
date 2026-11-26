"""Cola de revisión de casos: listar, tomar, decidir y auditar accesos."""

from datetime import datetime, timedelta, timezone

from ai.confianza import banda as banda_confianza
from storage.db import unidad_de_trabajo

ESTADOS_TERMINALES = {"validada", "corregida", "descartada", "expirada"}
DECISIONES = {
    "validar": "validada",
    "corregir": "corregida",
    "descartar": "descartada",
}


class ValidacionNoEncontrada(Exception):
    pass


class ConflictoValidacion(Exception):
    def __init__(self, detalle: dict):
        super().__init__("El caso ya no está disponible")
        self.detalle = detalle


class MotivoRequerido(Exception):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _futuro(horas: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat()


async def _una(db, validacion_id: int) -> dict | None:
    async with db.execute(
        "SELECT v.*, e.confianza_total, e.revision_requerida, "
        "e.motivo_revision, e.catalogo_nombre AS especialidad, "
        "e.turno_id, c.session_id, d.clave AS dominio "
        "FROM validacion v "
        "JOIN evidencia_turno e ON e.id = v.evidencia_turno_id "
        "JOIN consulta c ON c.id = v.consulta_id "
        "LEFT JOIN dominio d ON d.id = c.dominio_id "
        "WHERE v.id = ?",
        (validacion_id,),
    ) as cur:
        fila = await cur.fetchone()
    return dict(fila) if fila else None


def _conflicto(fila: dict | None) -> dict:
    if not fila:
        return {"estado": "inexistente"}
    return {
        "estado": fila.get("estado"),
        "asignado_a": fila.get("asignado_a"),
        "expira_en": fila.get("expira_en"),
        "version": fila.get("version"),
    }


async def listar(
    *,
    estado: str | None = None,
    especialidad: str | None = None,
    dominio: str | None = None,
    confianza_min: float | None = None,
    fecha: str | None = None,
    cursor: str | None = None,
    limite: int = 20,
) -> dict:
    limite = max(1, min(int(limite), 100))
    sql = (
        "SELECT v.id, v.estado, v.asignado_a, v.tomado_en, v.expira_en, "
        "v.version, v.creada_en, e.confianza_total, e.catalogo_nombre "
        "AS especialidad, e.motivo_revision, d.clave AS dominio, "
        "e.turno_id, c.session_id "
        "FROM validacion v "
        "JOIN evidencia_turno e ON e.id = v.evidencia_turno_id "
        "JOIN consulta c ON c.id = v.consulta_id "
        "LEFT JOIN dominio d ON d.id = c.dominio_id "
        "WHERE 1 = 1"
    )
    params: list = []

    if estado:
        sql += " AND v.estado = ?"
        params.append(estado)
    if especialidad:
        sql += " AND e.catalogo_nombre = ?"
        params.append(especialidad)
    if dominio:
        sql += " AND d.clave = ?"
        params.append(dominio)
    if confianza_min is not None:
        sql += " AND e.confianza_total >= ?"
        params.append(float(confianza_min))
    if fecha:
        sql += " AND v.creada_en >= ?"
        params.append(fecha)
    if cursor:
        try:
            creada, identificador = cursor.rsplit("|", 1)
            params.extend([creada, creada, int(identificador)])
            sql += (
                " AND (v.creada_en < ? OR (v.creada_en = ? AND v.id < ?))"
            )
        except (ValueError, TypeError):
            raise MotivoRequerido("cursor inválido")

    sql += " ORDER BY v.creada_en DESC, v.id DESC LIMIT ?"
    params.append(limite + 1)

    con = await _conectar()
    try:
        async with con.execute(sql, params) as cur:
            filas = [dict(f) for f in await cur.fetchall()]
    finally:
        await con.close()

    for fila in filas:
        fila["banda"] = banda_confianza(float(fila.get("confianza_total") or 0))

    siguiente = None
    if len(filas) > limite:
        ultima = filas[limite - 1]
        siguiente = f"{ultima['creada_en']}|{ultima['id']}"
        filas = filas[:limite]

    return {"items": filas, "next_cursor": siguiente, "limite": limite}


async def detalle(validacion_id: int) -> dict | None:
    con = await _conectar()
    try:
        fila = await _una(con, validacion_id)
        if not fila:
            return None

        async with con.execute(
            "SELECT * FROM evidencia_turno WHERE id = ?",
            (fila["evidencia_turno_id"],),
        ) as cur:
            evidencia = await cur.fetchone()
        async with con.execute(
            "SELECT nombre, valor, peso FROM evidencia_componente "
            "WHERE evidencia_id = ? ORDER BY id",
            (fila["evidencia_turno_id"],),
        ) as cur:
            componentes = [dict(f) for f in await cur.fetchall()]
        async with con.execute(
            "SELECT dominio_clave, score, rank FROM turno_dominio_candidato "
            "WHERE turno_id = ? ORDER BY rank",
            (fila["turno_id"],),
        ) as cur:
            candidatos = [dict(f) for f in await cur.fetchall()]
        async with con.execute(
            "SELECT actor_id, evento, detalle, creado_en "
            "FROM validacion_evento WHERE validacion_id = ? ORDER BY id",
            (validacion_id,),
        ) as cur:
            eventos = [dict(f) for f in await cur.fetchall()]
        async with con.execute(
            "SELECT actor_id, rol, accion, creado_en FROM acceso_caso "
            "WHERE validacion_id = ? ORDER BY id",
            (validacion_id,),
        ) as cur:
            accesos = [dict(f) for f in await cur.fetchall()]

        return {
            "validacion": fila,
            "evidencia": dict(evidencia) if evidencia else None,
            "componentes": componentes,
            "candidatos": candidatos,
            "eventos": eventos,
            "accesos": accesos,
        }
    finally:
        await con.close()


async def tomar(validacion_id: int, actor_id: str) -> dict:
    ahora = _ahora()
    expira = _futuro(48)

    async with unidad_de_trabajo() as db:
        cur = await db.execute(
            "UPDATE validacion SET estado = 'asignada', asignado_a = ?, "
            "tomado_en = ?, expira_en = ?, version = version + 1, "
            "actualizada_en = ? "
            "WHERE id = ? AND estado IN ('pendiente', 'asignada') "
            "AND (estado = 'pendiente' OR expira_en IS NULL OR expira_en < ?)",
            (actor_id, ahora, expira, ahora, validacion_id, ahora),
        )
        if cur.rowcount == 0:
            fila = await _una(db, validacion_id)
            raise ConflictoValidacion(_conflicto(fila))

        await db.execute(
            "INSERT INTO validacion_evento "
            "(validacion_id, actor_id, evento, detalle, creado_en) "
            "VALUES (?, ?, 'tomada', ?, ?)",
            (validacion_id, actor_id, expira, ahora),
        )
        return await _una(db, validacion_id)


async def decidir(
    validacion_id: int,
    actor_id: str,
    decision: str,
    motivo_codigo: str | None = None,
    comentario: str | None = None,
    version: int | None = None,
) -> dict:
    if decision not in DECISIONES:
        raise MotivoRequerido("decisión inválida")
    if decision in {"corregir", "descartar"} and not (motivo_codigo or "").strip():
        raise MotivoRequerido("motivo_codigo es obligatorio para corregir o descartar")

    nuevo_estado = DECISIONES[decision]
    ahora = _ahora()

    async with unidad_de_trabajo() as db:
        fila = await _una(db, validacion_id)
        if not fila:
            raise ValidacionNoEncontrada("validación no encontrada")
        if fila["estado"] in ESTADOS_TERMINALES:
            raise ConflictoValidacion(_conflicto(fila))
        if fila["asignado_a"] != actor_id:
            raise ConflictoValidacion(_conflicto(fila))
        if version is not None and int(version) != int(fila["version"]):
            raise ConflictoValidacion(_conflicto(fila))

        cur = await db.execute(
            "UPDATE validacion SET estado = ?, decision = ?, motivo_codigo = ?, "
            "comentario = ?, version = version + 1, actualizada_en = ? "
            "WHERE id = ? AND version = ? AND estado IN ('asignada', 'vista') "
            "AND asignado_a = ?",
            (
                nuevo_estado, decision, motivo_codigo, comentario, ahora,
                validacion_id, fila["version"], actor_id,
            ),
        )
        if cur.rowcount == 0:
            raise ConflictoValidacion(_conflicto(await _una(db, validacion_id)))

        await db.execute(
            "INSERT INTO validacion_evento "
            "(validacion_id, actor_id, evento, detalle, creado_en) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                validacion_id, actor_id, nuevo_estado,
                motivo_codigo or comentario, ahora,
            ),
        )
        return await _una(db, validacion_id)


async def visto(validacion_id: int, actor_id: str, rol: str | None = None) -> dict:
    ahora = _ahora()
    async with unidad_de_trabajo() as db:
        fila = await _una(db, validacion_id)
        if not fila:
            raise ValidacionNoEncontrada("validación no encontrada")

        await db.execute(
            "INSERT OR IGNORE INTO acceso_caso "
            "(validacion_id, actor_id, rol, accion, creado_en) "
            "VALUES (?, ?, ?, 'visto', ?)",
            (validacion_id, actor_id, rol, ahora),
        )

        if fila["estado"] == "asignada" and fila["asignado_a"] == actor_id:
            await db.execute(
                "UPDATE validacion SET estado = 'vista', version = version + 1, "
                "actualizada_en = ? WHERE id = ? AND estado = 'asignada'",
                (ahora, validacion_id),
            )
            await db.execute(
                "INSERT INTO validacion_evento "
                "(validacion_id, actor_id, evento, detalle, creado_en) "
                "VALUES (?, ?, 'vista', NULL, ?)",
                (validacion_id, actor_id, ahora),
            )

        return await _una(db, validacion_id)


async def liberar_expiradas() -> int:
    ahora = _ahora()
    liberadas = 0
    async with unidad_de_trabajo() as db:
        async with db.execute(
            "SELECT id FROM validacion WHERE estado = 'asignada' "
            "AND expira_en IS NOT NULL AND expira_en < ?",
            (ahora,),
        ) as cur:
            ids = [fila["id"] for fila in await cur.fetchall()]

        for validacion_id in ids:
            await db.execute(
                "UPDATE validacion SET estado = 'pendiente', asignado_a = NULL, "
                "tomado_en = NULL, expira_en = NULL, version = version + 1, "
                "actualizada_en = ? WHERE id = ? AND estado = 'asignada'",
                (ahora, validacion_id),
            )
            await db.execute(
                "INSERT INTO validacion_evento "
                "(validacion_id, actor_id, evento, detalle, creado_en) "
                "VALUES (?, NULL, 'expirada', NULL, ?)",
                (validacion_id, ahora),
            )
            liberadas += 1

    return liberadas


async def _conectar():
    from storage import db as db_mod

    return await db_mod.conectar()

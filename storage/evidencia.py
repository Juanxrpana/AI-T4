"""Evidencia reproducible por turno y casos de validación.

`guardar_evidencia()` y `crear_validacion()` reciben la conexión de
`storage.db.unidad_de_trabajo()`: no abren transacciones propias. Así la
evidencia, el mensaje del asistente, el outbox de auditoría y el cierre de la
consulta se confirman o se revierten juntos.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from storage import db as db_mod


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_json(datos) -> str:
    payload = json.dumps(
        datos, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_texto(texto: str) -> str:
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()


def estimar_confianza(componentes: list[dict]) -> float:
    """Promedio ponderado de componentes en 0..1."""
    pesos = [abs(float(c.get("peso", 0))) for c in componentes]
    total = sum(pesos)
    if not componentes or total == 0:
        return 0.0
    valor = sum(
        float(c.get("valor", 0)) * abs(float(c.get("peso", 0)))
        for c in componentes
    )
    return round(max(0.0, min(1.0, valor / total)), 4)


async def guardar_evidencia(
    db,
    *,
    turno_id: int,
    consulta_id: int,
    resumen_ficha: dict,
    respuesta_final: str,
    componentes: list[dict],
    candidatos: list[dict] | None = None,
    revision_requerida: bool = False,
    motivo_revision: str | None = None,
    confianza_total: float | None = None,
    modelo: str | None = None,
    catalogo_id: int | None = None,
    catalogo_nombre: str | None = None,
    prompt_version: str = "ficha-v1",
    scoring_version: str = "simple-v1",
    detector_version: str = "evidencia-v1",
    alarm_version: str = "alarma-v1",
) -> int:
    resumen_json = json.dumps(
        resumen_ficha, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    confianza = (
        float(confianza_total)
        if confianza_total is not None
        else estimar_confianza(componentes)
    )

    async with db.execute(
        "SELECT id FROM kb_version WHERE activa = 1 LIMIT 1"
    ) as cur:
        fila = await cur.fetchone()
    kb_version_id = fila["id"] if fila else None

    cur = await db.execute(
        "INSERT INTO evidencia_turno "
        "(turno_id, consulta_id, resumen_ficha, ficha_hash, respuesta_final, "
        " respuesta_hash, kb_version_id, prompt_version, prompt_hash, modelo, "
        " catalogo_id, catalogo_nombre, scoring_version, detector_version, "
        " alarm_version, confianza_total, revision_requerida, motivo_revision, "
        " creada_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            turno_id,
            consulta_id,
            resumen_json,
            hash_json(resumen_ficha),
            respuesta_final,
            hash_texto(respuesta_final),
            kb_version_id,
            prompt_version,
            hash_json({
                "dominio": resumen_ficha.get("dominio"),
                "respuestas": resumen_ficha.get("respuestas", {}),
            }),
            modelo,
            catalogo_id,
            catalogo_nombre,
            scoring_version,
            detector_version,
            alarm_version,
            confianza,
            1 if revision_requerida else 0,
            motivo_revision,
            ahora(),
        ),
    )
    evidencia_id = int(cur.lastrowid)

    for componente in componentes:
        await db.execute(
            "INSERT INTO evidencia_componente "
            "(evidencia_id, nombre, valor, peso) VALUES (?, ?, ?, ?)",
            (
                evidencia_id,
                componente.get("nombre", "desconocido"),
                float(componente.get("valor", 0)),
                float(componente.get("peso", 0)),
            ),
        )

    await db.execute(
        "DELETE FROM turno_dominio_candidato WHERE turno_id = ?", (turno_id,)
    )
    for rank, candidato in enumerate(candidatos or [], start=1):
        await db.execute(
            "INSERT INTO turno_dominio_candidato "
            "(turno_id, dominio_id, dominio_clave, score, rank) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                turno_id,
                candidato.get("dominio_id"),
                candidato.get("dominio") or candidato.get("dominio_clave", ""),
                float(candidato.get("score", 0)),
                rank,
            ),
        )

    return evidencia_id


async def crear_validacion(
    db,
    *,
    consulta_id: int,
    evidencia_turno_id: int,
    motivo: str,
) -> int:
    """Crea el caso pendiente y su evento inicial en la misma transacción."""
    creada = ahora()
    expira = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    cur = await db.execute(
        "INSERT INTO validacion "
        "(consulta_id, evidencia_turno_id, estado, version, motivo_codigo, "
        " creada_en, actualizada_en, expira_en) "
        "VALUES (?, ?, 'pendiente', 1, ?, ?, ?, ?)",
        (consulta_id, evidencia_turno_id, motivo, creada, creada, expira),
    )
    validacion_id = int(cur.lastrowid)
    await db.execute(
        "INSERT INTO validacion_evento "
        "(validacion_id, actor_id, evento, detalle, creado_en) "
        "VALUES (?, NULL, 'creada', ?, ?)",
        (validacion_id, motivo, creada),
    )
    return validacion_id


async def listar_por_turno(turno_id: int) -> dict | None:
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT * FROM evidencia_turno WHERE turno_id = ?", (turno_id,)
        ) as cur:
            fila = await cur.fetchone()
        if not fila:
            return None
        async with con.execute(
            "SELECT nombre, valor, peso FROM evidencia_componente "
            "WHERE evidencia_id = ? ORDER BY id",
            (fila["id"],),
        ) as cur:
            componentes = [dict(f) for f in await cur.fetchall()]
        async with con.execute(
            "SELECT dominio_id, dominio_clave, score, rank "
            "FROM turno_dominio_candidato WHERE turno_id = ? ORDER BY rank",
            (turno_id,),
        ) as cur:
            candidatos = [dict(f) for f in await cur.fetchall()]
        return {
            "evidencia": dict(fila),
            "componentes": componentes,
            "candidatos": candidatos,
        }
    finally:
        await con.close()

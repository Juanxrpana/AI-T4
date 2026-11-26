"""Auditoría append-only con outbox transaccional.

El turno escribe en `auditoria_outbox` dentro de la unidad de trabajo. El relay
mueve las filas pendientes a `auditoria` con `INSERT OR IGNORE` por
`idempotency_key`. Un fallo del relay se registra y se reintenta; no tumba el
turno ya confirmado.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from storage import db as db_mod

logger = logging.getLogger("asistente.auditoria")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


CAMPOS = (
    "session_id",
    "consulta_id",
    "turno_id",
    "usuario_id",
    "usuario_rol",
    "usuario_nombre",
    "paciente_id",
    "dominio",
    "consulta",
    "tipo_respuesta",
    "especialidad_sugerida",
    "pruebas_sugeridas",
    "modelo_usado",
    "latencia_ms",
    "tools_usadas",
    "json_respuesta",
    "resultado",
    "error_code",
)


def _serializar(evento: dict) -> dict:
    payload = {}
    for campo in CAMPOS:
        valor = evento.get(campo)
        if isinstance(valor, (list, dict)):
            valor = json.dumps(valor, ensure_ascii=False)
        payload[campo] = valor
    return payload


def _clave(payload: dict) -> str:
    texto = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


async def _insertar(db, payload: dict, clave: str | None) -> None:
    columnas = ["ts", "idempotency_key", *CAMPOS]
    valores = [_ahora(), clave, *[payload.get(campo) for campo in CAMPOS]]
    await db.execute(
        f"INSERT OR IGNORE INTO auditoria ({', '.join(columnas)}) "
        f"VALUES ({', '.join(['?'] * len(columnas))})",
        valores,
    )


async def registrar(
    evento: dict,
    *,
    db=None,
    idempotency_key: str | None = None,
) -> None:
    """Encola la auditoría.

    Con `db` (unidad de trabajo) escribe en el outbox y propaga el error para
    que la transacción completa se revierta. Sin `db` escribe directo, para
    compatibilidad con llamadas sueltas.
    """
    payload = _serializar(evento)
    clave = idempotency_key or _clave(payload)

    if db is None:
        con = await db_mod.conectar()
        try:
            await _insertar(con, payload, clave)
            await con.commit()
        finally:
            await con.close()
        return

    await db.execute(
        "INSERT OR IGNORE INTO auditoria_outbox "
        "(idempotency_key, payload_json, creado_en) VALUES (?, ?, ?)",
        (clave, json.dumps(payload, ensure_ascii=False), _ahora()),
    )


async def relay_auditoria(limite: int = 100) -> int:
    """Mueve outbox→auditoría. Devuelve cuántas filas se enviaron."""
    con = await db_mod.conectar()
    enviados = 0
    try:
        async with con.execute(
            "SELECT id, idempotency_key, payload_json FROM auditoria_outbox "
            "WHERE enviado_en IS NULL ORDER BY id LIMIT ?",
            (max(1, min(int(limite), 500)),),
        ) as cur:
            filas = await cur.fetchall()

        for fila in filas:
            try:
                payload = json.loads(fila["payload_json"])
            except ValueError:
                logger.exception(
                    "Outbox %s tiene payload inválido; se deja pendiente",
                    fila["id"],
                )
                continue

            try:
                await _insertar(con, payload, fila["idempotency_key"])
                await con.execute(
                    "UPDATE auditoria_outbox SET enviado_en = ? WHERE id = ?",
                    (_ahora(), fila["id"]),
                )
                enviados += 1
            except Exception:
                logger.exception("No se pudo relayar el outbox %s", fila["id"])

        await con.commit()
        return enviados
    finally:
        await con.close()


async def listar(limite: int = 50) -> list[dict]:
    limite = max(1, min(int(limite), 500))
    con = await db_mod.conectar()
    try:
        async with con.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)
        ) as cur:
            filas = await cur.fetchall()
        return [dict(f) for f in filas]
    finally:
        await con.close()

"""Auditoría append-only de las consultas (SQLite)."""

import json
from datetime import datetime, timezone

import aiosqlite

from storage.db import DB_PATH


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


CAMPOS = (
    "session_id",
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
)


async def registrar(evento: dict) -> None:
    valores = []
    for campo in CAMPOS:
        valor = evento.get(campo)
        if isinstance(valor, (list, dict)):
            valor = json.dumps(valor, ensure_ascii=False)
        valores.append(valor)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"INSERT INTO auditoria (ts, {', '.join(CAMPOS)}) "
            f"VALUES (?, {', '.join(['?'] * len(CAMPOS))})",
            [_ahora(), *valores],
        )
        await db.commit()


async def listar(limite: int = 50) -> list[dict]:
    limite = max(1, min(int(limite), 500))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)
        ) as cur:
            filas = await cur.fetchall()

    return [dict(f) for f in filas]

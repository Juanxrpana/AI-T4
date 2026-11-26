"""Ejecuta la semilla de la base de conocimiento.

Uso:
    python scripts/seed_kb.py

Es idempotente: si la KB ya tiene dominios, no reescribe nada.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import db  # noqa: E402


async def _main() -> None:
    await db.init_db()
    con = await db.conectar()
    try:
        async with con.execute(
            "SELECT id, hash, activa FROM kb_version ORDER BY id DESC LIMIT 1"
        ) as cur:
            version = await cur.fetchone()
        async with con.execute("SELECT COUNT(*) FROM dominio") as cur:
            dominios = (await cur.fetchone())[0]
        async with con.execute("SELECT COUNT(*) FROM dominio_pregunta") as cur:
            preguntas = (await cur.fetchone())[0]
    finally:
        await con.close()

    print(f"dominios={dominios} preguntas={preguntas}")
    if version:
        print(
            f"kb_version={version['id']} activa={version['activa']} "
            f"hash={version['hash'][:12]}"
        )


if __name__ == "__main__":
    asyncio.run(_main())

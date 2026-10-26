"""Persistencia local de MIDI (SQLite).

No toca MariaDB: guarda sesiones, mensajes, auditoría y resúmenes de memoria
del componente inteligente.
"""

import aiosqlite
from pathlib import Path

from config import settings

DB_PATH = Path(settings.SQLITE_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sesiones (
    session_id TEXT PRIMARY KEY,
    id_usuario TEXT,
    estado_json TEXT NOT NULL DEFAULT '{}',
    creada_en TEXT NOT NULL,
    actualizada_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    rol TEXT NOT NULL,
    texto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensajes_sesion ON mensajes(session_id);

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    session_id TEXT,
    usuario_id TEXT,
    usuario_rol TEXT,
    usuario_nombre TEXT,
    paciente_id TEXT,
    dominio TEXT,
    consulta TEXT,
    tipo_respuesta TEXT,
    especialidad_sugerida TEXT,
    pruebas_sugeridas TEXT,
    modelo_usado TEXT,
    latencia_ms INTEGER,
    tools_usadas TEXT,
    json_respuesta TEXT
);

CREATE TABLE IF NOT EXISTS memorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario TEXT NOT NULL,
    id_paciente TEXT NOT NULL DEFAULT '',
    resumen TEXT NOT NULL,
    datos_json TEXT,
    embedding TEXT,
    actualizada_en TEXT NOT NULL,
    UNIQUE (id_usuario, id_paciente)
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)

        # Migración: bases creadas antes de la memoria vectorizada.
        async with db.execute("PRAGMA table_info(memorias)") as cur:
            columnas = {fila[1] for fila in await cur.fetchall()}
        if "embedding" not in columnas:
            await db.execute("ALTER TABLE memorias ADD COLUMN embedding TEXT")

        await db.commit()

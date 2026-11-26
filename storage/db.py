"""Persistencia local de MIDI (SQLite).

No toca MariaDB: guarda sesiones, mensajes, auditoría y resúmenes de memoria
del componente inteligente.

A partir de la Fase 1 la base también guarda la base de conocimiento por tipo
(`storage/schema.sql`) y la identidad `consulta`/`turno`. El arranque es
fail-closed: si la KB queda vacía, el servicio no levanta.
"""

import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from config import settings

DB_PATH = Path(settings.SQLITE_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_RUTA_ESQUEMA = Path(__file__).with_name("schema.sql")
_DIR_MIGRACIONES = Path(__file__).with_name("migrations")

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


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checksum(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


async def conectar() -> aiosqlite.Connection:
    """Conexión con FKs activas y WAL para lecturas concurrentes."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("PRAGMA busy_timeout = 5000")
    return db


@asynccontextmanager
async def unidad_de_trabajo():
    """Transacción atómica para el cierre de un turno.

    Todo lo que se escriba con la conexión entregada se confirma junto o se
    revierte junto. No abrir conexiones propias dentro del bloque.
    """
    db = await conectar()
    try:
        await db.execute("BEGIN IMMEDIATE")
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


async def _columnas(db: aiosqlite.Connection, tabla: str) -> set[str]:
    async with db.execute(f"PRAGMA table_info({tabla})") as cur:
        return {fila[1] for fila in await cur.fetchall()}


async def _asegurar_columnas(db: aiosqlite.Connection) -> None:
    """Migraciones aditivas de bases creadas antes de la Fase 1."""
    columnas = await _columnas(db, "memorias")
    if "embedding" not in columnas:
        await db.execute("ALTER TABLE memorias ADD COLUMN embedding TEXT")

    columnas = await _columnas(db, "mensajes")
    if "consulta_id" not in columnas:
        await db.execute("ALTER TABLE mensajes ADD COLUMN consulta_id INTEGER")
    if "turno_id" not in columnas:
        await db.execute("ALTER TABLE mensajes ADD COLUMN turno_id INTEGER")

    columnas = await _columnas(db, "auditoria")
    for columna in (
        "consulta_id",
        "turno_id",
        "resultado",
        "error_code",
        "idempotency_key",
    ):
        if columna not in columnas:
            await db.execute(f"ALTER TABLE auditoria ADD COLUMN {columna}")

    columnas = await _columnas(db, "turno")
    if "respuesta_json" not in columnas:
        await db.execute("ALTER TABLE turno ADD COLUMN respuesta_json TEXT")


async def migrar(db: aiosqlite.Connection) -> None:
    """Aplica `storage/migrations/*.sql` en orden, una sola vez."""
    _DIR_MIGRACIONES.mkdir(parents=True, exist_ok=True)

    async with db.execute("SELECT version, checksum FROM schema_migrations") as cur:
        aplicadas = {fila["version"]: fila["checksum"] for fila in await cur.fetchall()}

    for ruta in sorted(_DIR_MIGRACIONES.glob("*.sql")):
        version = ruta.stem
        sql = ruta.read_text(encoding="utf-8")
        suma = _checksum(sql)
        if version in aplicadas:
            if aplicadas[version] != suma:
                raise RuntimeError(
                    f"La migración {version} cambió después de aplicarse "
                    f"(checksum {aplicadas[version]} != {suma})."
                )
            continue
        await db.executescript(sql)
        await db.execute(
            "INSERT INTO schema_migrations (version, checksum, aplicada_en) "
            "VALUES (?, ?, ?)",
            (version, suma, _ahora()),
        )
        await db.commit()


async def _registrar_baseline(db: aiosqlite.Connection) -> None:
    baseline = _RUTA_ESQUEMA.read_text(encoding="utf-8")
    suma = _checksum(SCHEMA + baseline)
    async with db.execute(
        "SELECT 1 FROM schema_migrations WHERE version = '000_schema'"
    ) as cur:
        if await cur.fetchone():
            return
    await db.execute(
        "INSERT INTO schema_migrations (version, checksum, aplicada_en) "
        "VALUES ('000_schema', ?, ?)",
        (suma, _ahora()),
    )
    await db.commit()


async def _validar_kb(db: aiosqlite.Connection) -> None:
    async with db.execute(
        "SELECT COUNT(*) FROM dominio d "
        "WHERE d.activo = 1 AND EXISTS ("
        "  SELECT 1 FROM dominio_pregunta p "
        "  WHERE p.dominio_id = d.id AND p.activo = 1 "
        "  AND p.estado = 'aprobado'"
        ")"
    ) as cur:
        total = (await cur.fetchone())[0]
    if not total:
        raise RuntimeError(
            "La base de conocimiento quedó vacía o sin preguntas aprobadas. "
            "Ejecuta `python scripts/seed_kb.py` antes de arrancar."
        )


async def init_db() -> None:
    db = await conectar()
    try:
        await db.executescript(SCHEMA)
        await db.executescript(_RUTA_ESQUEMA.read_text(encoding="utf-8"))
        await _asegurar_columnas(db)
        await migrar(db)
        await _registrar_baseline(db)
        await db.commit()

        from storage import seed_kb

        await seed_kb.sembrar_si_vacio(db)
        await _validar_kb(db)
        await db.commit()

        from storage import conocimiento

        conocimiento.invalidar_cache()
    finally:
        await db.close()

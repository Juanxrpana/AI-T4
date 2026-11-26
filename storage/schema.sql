-- Esquema incremental de MIDI (Fase 1: base de conocimiento por tipo e
-- identidad consulta/turno). Es idempotente: se ejecuta en cada arranque
-- después del esquema base de `storage/db.py`.
--
-- Reglas de datos:
-- * Cada tabla de lista tiene `activo` y `estado`; el loader solo lee
--   `activo = 1 AND estado = 'aprobado'`.
-- * Las palabras y señales conservan sus alias con `alias_de`; la detección
--   usa únicamente las filas canónicas (`alias_de IS NULL`).
-- * `kb_version.activa` es única por índice parcial.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    aplicada_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dominio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    min_preguntas INTEGER NOT NULL DEFAULT 3,
    max_preguntas INTEGER NOT NULL DEFAULT 5,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dominio_palabra_clave (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    valor TEXT NOT NULL,
    valor_normalizado TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'seed'
        CHECK (origen IN ('seed', 'aprendido', 'propuesta')),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    alias_de INTEGER NULL REFERENCES dominio_palabra_clave(id) ON DELETE SET NULL,
    creado_en TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_palabra_canonica
    ON dominio_palabra_clave(dominio_id, valor_normalizado)
    WHERE alias_de IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_palabra_alias
    ON dominio_palabra_clave(dominio_id, valor_normalizado)
    WHERE alias_de IS NOT NULL;

CREATE TABLE IF NOT EXISTS dominio_senal_alarma (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    valor TEXT NOT NULL,
    valor_normalizado TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'seed'
        CHECK (origen IN ('seed', 'aprendido', 'propuesta')),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    alias_de INTEGER NULL REFERENCES dominio_senal_alarma(id) ON DELETE SET NULL,
    creado_en TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_senal_canonica
    ON dominio_senal_alarma(dominio_id, valor_normalizado)
    WHERE alias_de IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_senal_alias
    ON dominio_senal_alarma(dominio_id, valor_normalizado)
    WHERE alias_de IS NOT NULL;

CREATE TABLE IF NOT EXISTS dominio_pregunta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    clave TEXT NOT NULL,
    texto TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, clave)
);

CREATE TABLE IF NOT EXISTS dominio_especialidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, nombre_normalizado)
);

CREATE TABLE IF NOT EXISTS dominio_prueba (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, nombre_normalizado)
);

CREATE TABLE IF NOT EXISTS dominio_asociacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    valor TEXT NOT NULL,
    valor_normalizado TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, valor_normalizado)
);

CREATE TABLE IF NOT EXISTS dominio_descartar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    valor TEXT NOT NULL,
    valor_normalizado TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, valor_normalizado)
);

CREATE TABLE IF NOT EXISTS dominio_ejemplo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dominio_id INTEGER NOT NULL REFERENCES dominio(id) ON DELETE RESTRICT,
    texto TEXT NOT NULL,
    texto_normalizado TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'seed'
        CHECK (origen IN ('seed', 'aprendido', 'propuesta')),
    creado_por TEXT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    estado TEXT NOT NULL DEFAULT 'aprobado'
        CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
    creado_en TEXT NOT NULL,
    UNIQUE (dominio_id, texto_normalizado)
);

CREATE TABLE IF NOT EXISTS kb_version (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion TEXT NOT NULL,
    autor TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    normalizer_version TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    creada_en TEXT NOT NULL,
    activa INTEGER NOT NULL DEFAULT 0 CHECK (activa IN (0, 1))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_kb_version_activa
    ON kb_version(activa) WHERE activa = 1;

CREATE TABLE IF NOT EXISTS kb_version_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_version_id INTEGER NOT NULL REFERENCES kb_version(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'palabra', 'senal', 'pregunta', 'especialidad', 'prueba',
        'asociacion', 'descartar', 'ejemplo'
    )),
    elemento_id INTEGER NOT NULL,
    dominio_id INTEGER,
    clave TEXT,
    valor TEXT,
    valor_normalizado TEXT,
    estado TEXT,
    alias_de INTEGER
);
CREATE INDEX IF NOT EXISTS idx_kb_item_version
    ON kb_version_item(kb_version_id);

CREATE TABLE IF NOT EXISTS consulta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NULL REFERENCES sesiones(session_id) ON DELETE SET NULL,
    id_usuario TEXT,
    flujo TEXT NOT NULL DEFAULT 'general'
        CHECK (flujo IN ('general', 'cuestionario')),
    dominio_id INTEGER NULL REFERENCES dominio(id) ON DELETE SET NULL,
    id_paciente TEXT,
    estado TEXT NOT NULL DEFAULT 'abierta'
        CHECK (estado IN ('abierta', 'cerrada')),
    motivo_cierre TEXT,
    creada_en TEXT NOT NULL,
    cerrada_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_consulta_sesion ON consulta(session_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_consulta_abierta
    ON consulta(session_id) WHERE estado = 'abierta';

CREATE TABLE IF NOT EXISTS turno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id INTEGER NOT NULL REFERENCES consulta(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    peticion_id TEXT NOT NULL UNIQUE,
    rol TEXT NOT NULL DEFAULT 'user',
    texto TEXT NOT NULL DEFAULT '',
    tipo_respuesta TEXT,
    origen_respuesta TEXT,
    degradado INTEGER NOT NULL DEFAULT 0 CHECK (degradado IN (0, 1)),
    respuesta_json TEXT,
    creado_en TEXT NOT NULL,
    UNIQUE (consulta_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_turno_consulta ON turno(consulta_id);

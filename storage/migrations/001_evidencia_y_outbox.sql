-- Fase 2: evidencia reproducible por turno, candidatos de dominio, casos de
-- validación y outbox de auditoría.
--
-- `auditoria.idempotency_key` se añade de forma idempotente en
-- `storage/db._asegurar_columnas`; aquí solo se crea su índice único.

CREATE TABLE IF NOT EXISTS evidencia_turno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno_id INTEGER NOT NULL UNIQUE REFERENCES turno(id) ON DELETE CASCADE,
    consulta_id INTEGER NOT NULL REFERENCES consulta(id) ON DELETE CASCADE,
    resumen_ficha TEXT NOT NULL,
    ficha_hash TEXT NOT NULL,
    respuesta_final TEXT NOT NULL,
    respuesta_hash TEXT NOT NULL,
    kb_version_id INTEGER REFERENCES kb_version(id) ON DELETE SET NULL,
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    modelo TEXT,
    catalogo_id INTEGER,
    catalogo_nombre TEXT,
    scoring_version TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    alarm_version TEXT NOT NULL,
    confianza_total REAL NOT NULL DEFAULT 0
        CHECK (confianza_total >= 0 AND confianza_total <= 1),
    revision_requerida INTEGER NOT NULL DEFAULT 0
        CHECK (revision_requerida IN (0, 1)),
    motivo_revision TEXT,
    creada_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidencia_consulta
    ON evidencia_turno(consulta_id);

CREATE TABLE IF NOT EXISTS evidencia_componente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidencia_id INTEGER NOT NULL
        REFERENCES evidencia_turno(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    valor REAL NOT NULL,
    peso REAL NOT NULL,
    UNIQUE (evidencia_id, nombre)
);

CREATE TABLE IF NOT EXISTS turno_dominio_candidato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turno_id INTEGER NOT NULL REFERENCES turno(id) ON DELETE CASCADE,
    dominio_id INTEGER REFERENCES dominio(id) ON DELETE SET NULL,
    dominio_clave TEXT NOT NULL,
    score REAL NOT NULL,
    rank INTEGER NOT NULL,
    UNIQUE (turno_id, rank)
);

CREATE TABLE IF NOT EXISTS validacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id INTEGER NOT NULL REFERENCES consulta(id) ON DELETE CASCADE,
    evidencia_turno_id INTEGER NOT NULL UNIQUE
        REFERENCES evidencia_turno(id) ON DELETE CASCADE,
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN (
            'pendiente', 'asignada', 'vista', 'validada',
            'corregida', 'descartada', 'expirada'
        )),
    asignado_a TEXT,
    tomado_en TEXT,
    expira_en TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    decision TEXT,
    motivo_codigo TEXT,
    comentario TEXT,
    creada_en TEXT NOT NULL,
    actualizada_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_validacion_estado
    ON validacion(estado, creada_en);
CREATE INDEX IF NOT EXISTS idx_validacion_asignado
    ON validacion(asignado_a, expira_en);

CREATE TABLE IF NOT EXISTS validacion_evento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validacion_id INTEGER NOT NULL
        REFERENCES validacion(id) ON DELETE CASCADE,
    actor_id TEXT,
    evento TEXT NOT NULL,
    detalle TEXT,
    creado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_validacion_evento
    ON validacion_evento(validacion_id);

CREATE TABLE IF NOT EXISTS auditoria_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    enviado_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_pendiente
    ON auditoria_outbox(enviado_en) WHERE enviado_en IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_auditoria_idem
    ON auditoria(idempotency_key);

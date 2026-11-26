-- Fase 3: acceso a casos y propuestas de conocimiento.

CREATE TABLE IF NOT EXISTS acceso_caso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validacion_id INTEGER NOT NULL
        REFERENCES validacion(id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    rol TEXT,
    accion TEXT NOT NULL DEFAULT 'visto',
    creado_en TEXT NOT NULL,
    UNIQUE (validacion_id, actor_id, accion)
);
CREATE INDEX IF NOT EXISTS idx_acceso_actor
    ON acceso_caso(actor_id, creado_en);

CREATE TABLE IF NOT EXISTS propuesta_conocimiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id INTEGER REFERENCES consulta(id) ON DELETE SET NULL,
    evidencia_turno_id INTEGER
        REFERENCES evidencia_turno(id) ON DELETE SET NULL,
    validacion_id INTEGER REFERENCES validacion(id) ON DELETE SET NULL,
    dominio_clave TEXT NOT NULL,
    dominio_id INTEGER REFERENCES dominio(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL
        CHECK (tipo IN ('palabra', 'senal', 'pregunta', 'ejemplo')),
    clave TEXT,
    valor TEXT NOT NULL,
    valor_normalizado TEXT NOT NULL,
    capa_error TEXT NOT NULL DEFAULT 'conocimiento'
        CHECK (capa_error IN (
            'percepcion', 'conocimiento', 'politica', 'tecnica', 'otra'
        )),
    estado TEXT NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'aprobada', 'rechazada')),
    generado_por TEXT,
    aprobado_por TEXT,
    motivo_rechazo TEXT,
    creada_en TEXT NOT NULL,
    resuelta_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_propuesta_estado
    ON propuesta_conocimiento(estado, creada_en);
CREATE UNIQUE INDEX IF NOT EXISTS ux_propuesta_pendiente
    ON propuesta_conocimiento(dominio_id, tipo, valor_normalizado)
    WHERE estado = 'pendiente';

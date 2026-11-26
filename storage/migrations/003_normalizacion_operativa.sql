-- Fase 4: normalización operativa aditiva.
--
-- Las columnas JSON se conservan como contrato de compatibilidad. Las tablas
-- hijas se llenan con backfill y se mantienen sincronizadas con triggers, de
-- modo que el runtime actual no cambia de comportamiento.
--
-- `json_each` entrega el valor SQL (texto sin comillas, 1/0 para booleanos).
-- Para guardar JSON válido se usa `json_quote` salvo en booleanos/nulos, que
-- se reconstruyen con su literal.

CREATE TABLE IF NOT EXISTS sesion_estado (
    session_id TEXT NOT NULL
        REFERENCES sesiones(session_id) ON DELETE CASCADE,
    clave TEXT NOT NULL,
    valor_json TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    PRIMARY KEY (session_id, clave)
);

CREATE TABLE IF NOT EXISTS memoria_dato (
    memoria_id INTEGER NOT NULL
        REFERENCES memorias(id) ON DELETE CASCADE,
    clave TEXT NOT NULL,
    valor_json TEXT NOT NULL,
    PRIMARY KEY (memoria_id, clave)
);

CREATE TABLE IF NOT EXISTS memoria_embedding (
    memoria_id INTEGER NOT NULL
        REFERENCES memorias(id) ON DELETE CASCADE,
    indice INTEGER NOT NULL,
    valor REAL NOT NULL,
    PRIMARY KEY (memoria_id, indice)
);

CREATE TABLE IF NOT EXISTS auditoria_respuesta (
    auditoria_id INTEGER NOT NULL
        REFERENCES auditoria(id) ON DELETE CASCADE,
    clave TEXT NOT NULL,
    valor_json TEXT NOT NULL,
    PRIMARY KEY (auditoria_id, clave)
);

-- Backfill de los datos existentes.
INSERT OR IGNORE INTO sesion_estado
    (session_id, clave, valor_json, actualizado_en)
SELECT s.session_id, j.key,
       CASE j.type
           WHEN 'true' THEN 'true'
           WHEN 'false' THEN 'false'
           WHEN 'null' THEN 'null'
           WHEN 'object' THEN j.value
           WHEN 'array' THEN j.value
           ELSE json_quote(j.value)
       END,
       s.actualizada_en
FROM sesiones s,
     json_each(CASE WHEN json_valid(s.estado_json)
                    THEN s.estado_json ELSE '{}' END) j;

INSERT OR IGNORE INTO memoria_dato (memoria_id, clave, valor_json)
SELECT m.id, j.key,
       CASE j.type
           WHEN 'true' THEN 'true'
           WHEN 'false' THEN 'false'
           WHEN 'null' THEN 'null'
           WHEN 'object' THEN j.value
           WHEN 'array' THEN j.value
           ELSE json_quote(j.value)
       END
FROM memorias m,
     json_each(CASE WHEN json_valid(m.datos_json)
                    THEN m.datos_json ELSE '{}' END) j
WHERE m.datos_json IS NOT NULL;

INSERT OR IGNORE INTO memoria_embedding (memoria_id, indice, valor)
SELECT m.id, CAST(j.key AS INTEGER), CAST(j.value AS REAL)
FROM memorias m,
     json_each(CASE WHEN json_valid(m.embedding)
                    THEN m.embedding ELSE '[]' END) j
WHERE m.embedding IS NOT NULL;

INSERT OR IGNORE INTO auditoria_respuesta (auditoria_id, clave, valor_json)
SELECT a.id, j.key,
       CASE j.type
           WHEN 'true' THEN 'true'
           WHEN 'false' THEN 'false'
           WHEN 'null' THEN 'null'
           WHEN 'object' THEN j.value
           WHEN 'array' THEN j.value
           ELSE json_quote(j.value)
       END
FROM auditoria a,
     json_each(CASE WHEN json_valid(a.json_respuesta)
                    THEN a.json_respuesta ELSE '{}' END) j
WHERE a.json_respuesta IS NOT NULL;

-- Sincronización futura: sesiones.estado_json.
CREATE TRIGGER IF NOT EXISTS trg_sesiones_estado_ai
AFTER INSERT ON sesiones
BEGIN
    INSERT OR REPLACE INTO sesion_estado
        (session_id, clave, valor_json, actualizado_en)
    SELECT NEW.session_id, j.key,
           CASE j.type
               WHEN 'true' THEN 'true'
               WHEN 'false' THEN 'false'
               WHEN 'null' THEN 'null'
               WHEN 'object' THEN j.value
               WHEN 'array' THEN j.value
               ELSE json_quote(j.value)
           END,
           NEW.actualizada_en
    FROM json_each(CASE WHEN json_valid(NEW.estado_json)
                        THEN NEW.estado_json ELSE '{}' END) j;
END;

CREATE TRIGGER IF NOT EXISTS trg_sesiones_estado_au
AFTER UPDATE OF estado_json ON sesiones
BEGIN
    DELETE FROM sesion_estado WHERE session_id = NEW.session_id;
    INSERT OR REPLACE INTO sesion_estado
        (session_id, clave, valor_json, actualizado_en)
    SELECT NEW.session_id, j.key,
           CASE j.type
               WHEN 'true' THEN 'true'
               WHEN 'false' THEN 'false'
               WHEN 'null' THEN 'null'
               WHEN 'object' THEN j.value
               WHEN 'array' THEN j.value
               ELSE json_quote(j.value)
           END,
           NEW.actualizada_en
    FROM json_each(CASE WHEN json_valid(NEW.estado_json)
                        THEN NEW.estado_json ELSE '{}' END) j;
END;

-- Sincronización futura: memorias.datos_json.
CREATE TRIGGER IF NOT EXISTS trg_memorias_datos_ai
AFTER INSERT ON memorias
BEGIN
    INSERT OR REPLACE INTO memoria_dato (memoria_id, clave, valor_json)
    SELECT NEW.id, j.key,
           CASE j.type
               WHEN 'true' THEN 'true'
               WHEN 'false' THEN 'false'
               WHEN 'null' THEN 'null'
               WHEN 'object' THEN j.value
               WHEN 'array' THEN j.value
               ELSE json_quote(j.value)
           END
    FROM json_each(CASE WHEN json_valid(NEW.datos_json)
                        THEN NEW.datos_json ELSE '{}' END) j;
END;

CREATE TRIGGER IF NOT EXISTS trg_memorias_datos_au
AFTER UPDATE OF datos_json ON memorias
BEGIN
    DELETE FROM memoria_dato WHERE memoria_id = NEW.id;
    INSERT OR REPLACE INTO memoria_dato (memoria_id, clave, valor_json)
    SELECT NEW.id, j.key,
           CASE j.type
               WHEN 'true' THEN 'true'
               WHEN 'false' THEN 'false'
               WHEN 'null' THEN 'null'
               WHEN 'object' THEN j.value
               WHEN 'array' THEN j.value
               ELSE json_quote(j.value)
           END
    FROM json_each(CASE WHEN json_valid(NEW.datos_json)
                        THEN NEW.datos_json ELSE '{}' END) j;
END;

-- Sincronización futura: memorias.embedding.
CREATE TRIGGER IF NOT EXISTS trg_memorias_embedding_ai
AFTER INSERT ON memorias
BEGIN
    INSERT OR REPLACE INTO memoria_embedding (memoria_id, indice, valor)
    SELECT NEW.id, CAST(j.key AS INTEGER), CAST(j.value AS REAL)
    FROM json_each(CASE WHEN json_valid(NEW.embedding)
                        THEN NEW.embedding ELSE '[]' END) j;
END;

CREATE TRIGGER IF NOT EXISTS trg_memorias_embedding_au
AFTER UPDATE OF embedding ON memorias
BEGIN
    DELETE FROM memoria_embedding WHERE memoria_id = NEW.id;
    INSERT OR REPLACE INTO memoria_embedding (memoria_id, indice, valor)
    SELECT NEW.id, CAST(j.key AS INTEGER), CAST(j.value AS REAL)
    FROM json_each(CASE WHEN json_valid(NEW.embedding)
                        THEN NEW.embedding ELSE '[]' END) j;
END;

-- Sincronización futura: auditoria.json_respuesta (append-only).
CREATE TRIGGER IF NOT EXISTS trg_auditoria_respuesta_ai
AFTER INSERT ON auditoria
BEGIN
    INSERT OR REPLACE INTO auditoria_respuesta (auditoria_id, clave, valor_json)
    SELECT NEW.id, j.key,
           CASE j.type
               WHEN 'true' THEN 'true'
               WHEN 'false' THEN 'false'
               WHEN 'null' THEN 'null'
               WHEN 'object' THEN j.value
               WHEN 'array' THEN j.value
               ELSE json_quote(j.value)
           END
    FROM json_each(CASE WHEN json_valid(NEW.json_respuesta)
                        THEN NEW.json_respuesta ELSE '{}' END) j;
END;

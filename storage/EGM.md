# Persistencia local de MIDI (`storage`)

## Overview

`storage` guarda todo el estado operativo del componente en SQLite mediante `aiosqlite`: base de conocimiento por tipo, sesiones, identidad `consulta`/`turno`, evidencia, validación, propuestas, memoria y auditoría con outbox. No es la base clínica y no abre MariaDB.

El archivo por defecto es `storage/midi.db`, configurable con `SQLITE_PATH`. La conexión activa FKs, WAL y `busy_timeout`; el arranque ejecuta `schema.sql` y las migraciones de `storage/migrations/` y es fail-closed si la KB queda vacía.

## Interface

### `storage/db.py`

- `DB_PATH`: `Path(settings.SQLITE_PATH)`.
- `SCHEMA`: DDL base de `sesiones`, `mensajes`, `auditoria` y `memorias`.
- `conectar()`: abre `aiosqlite` con `foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout=5000` y `row_factory`.
- `unidad_de_trabajo()`: context manager con `BEGIN IMMEDIATE`, commit y rollback.
- `migrar(db)`: aplica `storage/migrations/*.sql` en orden y valida checksums.
- `init_db()`: crea esquema, asegura columnas aditivas, migra, siembra la KB si está vacía y valida que existan dominios con preguntas.

### `storage/schema.sql`

Tablas de KB e identidad: `dominio`, `dominio_palabra_clave`, `dominio_senal_alarma`, `dominio_pregunta`, `dominio_especialidad`, `dominio_prueba`, `dominio_asociacion`, `dominio_descartar`, `dominio_ejemplo`, `kb_version`, `kb_version_item`, `consulta`, `turno` y `schema_migrations`.

### `storage/migrations/`

- `001_evidencia_y_outbox.sql`: `evidencia_turno`, `evidencia_componente`, `turno_dominio_candidato`, `validacion`, `validacion_evento`, `auditoria_outbox` e índice único de auditoría.
- `002_validaciones_propuestas.sql`: `acceso_caso` y `propuesta_conocimiento`.
- `003_normalizacion_operativa.sql`: `sesion_estado`, `memoria_dato`, `memoria_embedding`, `auditoria_respuesta`, backfill y triggers.

### `storage/conocimiento.py`

- `snapshot_sincrono(recargar=False)`: KB activa con la forma del antiguo `dominios.json`.
- `invalidar_cache()`, `id_dominio(clave)`.
- `listar_aprendido()`: palabras/ejemplos con `origen = 'aprendido'`.
- `agregar_ejemplo(dominio, frase)`, `agregar_palabra(dominio, palabra)`.
- `publicar_version(descripcion, autor)`: crea o reactiva una `kb_version` con snapshot e ítems.

### `storage/seed_kb.py`

- `sembrar_si_vacio(con)`: siembra solo si `dominio` está vacío.
- `sembrar(con)`: lee `knowledge/dominios.json` y `knowledge/aprendido.json`, separa canónicos/alias, inserta por tipo y publica la versión inicial.

### `storage/sesiones.py`

- `obtener_sesion`, `crear_sesion`, `guardar_estado`.
- `agregar_mensaje`, `listar_mensajes`, `historial_para_gemini`, `borrar_sesion`.
- `obtener_o_crear_consulta`, `obtener_turno_por_peticion`, `crear_turno`, `actualizar_turno`, `actualizar_consulta`, `cerrar_consulta`.
- `PeticionIdConflicto`: evita reutilizar una clave en otra consulta/sesión.

### `storage/evidencia.py`

- `hash_json`, `hash_texto`, `estimar_confianza`.
- `guardar_evidencia(db, ...)`: inserta evidencia, componentes y candidatos; usa la conexión de la UoW.
- `crear_validacion(db, ...)`: crea el caso y su evento inicial.
- `listar_por_turno(turno_id)`.

### `storage/validaciones.py`

- `listar`, `detalle`, `tomar`, `decidir`, `visto`, `liberar_expiradas`.
- Excepciones `ValidacionNoEncontrada`, `ConflictoValidacion`, `MotivoRequerido`.

### `storage/propuestas.py`

- `crear`, `listar`, `aprobar`, `rechazar`.
- Excepciones `PropuestaNoEncontrada`, `ConflictoPropuesta`, `Autoaprobacion`.

### `storage/auditoria.py`

- `registrar(evento, db=None, idempotency_key=None)`: con `db` escribe en `auditoria_outbox`; sin `db` escribe directo.
- `relay_auditoria(limite=100)`: mueve outbox a `auditoria` con `INSERT OR IGNORE`.
- `listar(limite=50)`.

### `storage/memoria.py`

- `guardar`, `obtener`, `actualizar_embedding`, `buscar_similares`, `borrar`.

### `storage/normalizacion.py`

- `leer_estado`, `leer_datos_memoria`, `leer_embedding`, `leer_respuesta`: lectores de las tablas sombra.

## Invariants

- **SQLite local.** No hay conexión a MariaDB ni escritura en la base clínica.
- **FK y WAL.** `conectar()` activa FKs, WAL y `busy_timeout`; las pruebas y la verificación de migración comprueban `foreign_key_check`.
- **UoW del turno.** Evidencia, mensaje, validación, cierre y outbox se escriben en una sola transacción; un fallo revierte todo y el endpoint responde `503`.
- **Una evidencia por turno.** `evidencia_turno.turno_id` es `UNIQUE`.
- **Idempotencia.** `turno.peticion_id` es único; una respuesta previa se guarda en `turno.respuesta_json` y se reproduce.
- **Auditoría outbox.** `auditoria.idempotency_key` es único; el relay es reintentable y no duplica filas.
- **Validación.** El lease es de 48 h; solo se retoma si está `pendiente` o `asignada` vencida; las decisiones usan versión optimista.
- **Propuestas.** No hay autoaprobación; aprobar publica una `kb_version`.
- **KB sembrada.** `init_db` falla si no hay dominios con preguntas aprobadas.
- **JSON de compatibilidad.** Las columnas JSON siguen siendo el contrato; las tablas normalizadas se mantienen por triggers.
- **Fechas UTC.** Se generan con `datetime.now(timezone.utc).isoformat()`.

## Side Effects

- Creación del directorio y archivo SQLite.
- Ejecución de migraciones y triggers.
- Escritura/lectura de KB, sesiones, consultas, turnos, evidencia, validación, propuestas, memoria, auditoría y outbox.
- WAL y archivos `-wal`/`-shm` de SQLite.
- Sin llamadas HTTP, sin MySQL y sin archivos clínicos fuera de SQLite.

## Verification

- Run: `python -m pytest -q`
- Pruebas específicas: `tests/test_migracion_kb.py`, `tests/test_identidad.py`, `tests/test_evidencia_turno.py`, `tests/test_transaccion.py`, `tests/test_validaciones.py`, `tests/test_propuestas.py`, `tests/test_normalizacion_operativa.py`.
- Migración: probar sobre una copia de `storage/midi.db`; `PRAGMA foreign_key_check` debe devolver `[]`.

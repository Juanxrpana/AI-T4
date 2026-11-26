# Persistencia local de MIDI (`storage`)

## Overview

`storage` guarda el estado operativo del componente en SQLite mediante `aiosqlite`: sesiones, mensajes, memoria por usuario/paciente y auditoría append-only. No es la base clínica y no sustituye a MariaDB. El archivo por defecto es `storage/midi.db`, configurable con `SQLITE_PATH`.

`storage/db.py` crea el directorio padre de `DB_PATH` al importarse; el archivo SQLite se crea al conectar o al ejecutar `init_db()` desde el `lifespan` de FastAPI.

## Interface

### `storage/db.py`

- `DB_PATH`: `Path(settings.SQLITE_PATH)`.
- `SCHEMA`: DDL de `sesiones`, `mensajes`, `auditoria` y `memorias`; incluye `idx_mensajes_sesion`.
- `init_db()`: ejecuta `SCHEMA` y migra bases antiguas agregando `memorias.embedding` si falta.

### `storage/sesiones.py`

- `obtener_sesion(session_id)`: devuelve `session_id`, `id_usuario` y `estado` deserializado; `None` si no existe.
- `crear_sesion(session_id, id_usuario, estado=None)`: `INSERT` con `ON CONFLICT` que conserva `id_usuario` anterior si el nuevo es nulo.
- `guardar_estado(session_id, estado)`: `UPDATE` de `estado_json` y `actualizada_en`; no crea la sesión si no existe.
- `agregar_mensaje(session_id, rol, texto)`: inserta un mensaje con fecha UTC.
- `listar_mensajes(session_id, limite=50)`: últimos `limite` mensajes, devueltos en orden cronológico.
- `historial_para_gemini(session_id, limite=12)`: adapta los mensajes a `{"role", "text"}`.
- `borrar_sesion(session_id)`: elimina mensajes y sesión; no toca auditoría.

### `storage/memoria.py`

- `guardar(id_usuario, id_paciente, resumen, datos=None)`: `UPSERT` por `(id_usuario, id_paciente)`; normaliza paciente nulo a `""`.
- `obtener(id_usuario, id_paciente)`: devuelve resumen, datos y embedding deserializados; `None` si no existe.
- `actualizar_embedding(id_usuario, id_paciente, embedding)`: actualiza solo el vector; no hace nada si el vector viene vacío.
- `buscar_similares(id_usuario, vector, k=5)`: carga las memorias con embedding del usuario y las ordena por similitud coseno en Python.
- `borrar(id_usuario, id_paciente=None)`: borra la memoria de un paciente o todas las del usuario.

### `storage/auditoria.py`

- `CAMPOS`: columnas auditables (`session_id`, usuario, paciente, dominio, consulta, tipo, especialidad, pruebas, modelo, latencia, tools y JSON de respuesta).
- `registrar(evento)`: inserta una fila; serializa listas y diccionarios a JSON.
- `listar(limite=50)`: devuelve las últimas filas; acota `limite` entre 1 y 500.

### `storage/__init__.py`

- Expone `init_db` y `DB_PATH`. `main.py` importa los submódulos `sesiones`, `memoria` y `auditoria` directamente (`from storage import auditoria, memoria, sesiones`).

## Invariants

- **SQLite local.** El archivo vive en `settings.SQLITE_PATH` (`storage/midi.db` por defecto). No hay conexión a MariaDB.
- **Sin claves foráneas declaradas.** `mensajes`, `auditoria` y `memorias` se relacionan por valor; la integridad la sostiene la aplicación.
- **`guardar_estado` no crea sesiones.** Solo actualiza una fila existente. El flujo de `main.py` crea la sesión antes de procesar.
- **Sesión y mensajes.** Borrar una sesión elimina sus mensajes en la misma operación; la auditoría se conserva.
- **Historial acotado.** `historial_para_gemini` devuelve como máximo el límite solicitado (12 por defecto) y en orden cronológico.
- **Memoria única.** `memorias` tiene `UNIQUE (id_usuario, id_paciente)`. Un paciente nulo se guarda como cadena vacía.
- **Embedding opcional.** `embedding` puede ser `NULL`; `buscar_similares` ignora las filas sin vector. El cálculo se hace en segundo plano desde `main.py`.
- **Auditoría append-only.** La API solo expone `GET /auditoria`; no hay endpoint de actualización ni de borrado. `registrar` no verifica duplicados.
- **JSON serializado.** `estado_json`, `datos_json`, `embedding`, `pruebas_sugeridas` y `json_respuesta` se guardan como texto JSON; los lectores toleran JSON inválido devolviendo valores vacíos.
- **Fechas UTC.** Todas las fechas se generan con `datetime.now(timezone.utc).isoformat()`.
- **Sin control de roles.** `storage` no autoriza; la autorización depende de la API key y de los headers del proxy.
- **Base creada al conectar.** `storage/db.py` crea el directorio de `DB_PATH` al importarse; el archivo se crea al abrir la primera conexión o al ejecutar `init_db()`.

## Side Effects

- Creación del directorio y del archivo SQLite si no existen.
- Lectura y escritura de `sesiones`, `mensajes`, `memorias` y `auditoria`.
- Migración automática de `memorias.embedding` en bases antiguas.
- Sin escritura en MySQL, sin archivos clínicos y sin llamadas HTTP.
- Los datos pueden contener información clínica; la política de retención y borrado queda fuera de este módulo.

## Verification

- Run: `pytest`
- Pruebas relacionadas: `tests/test_memoria.py`, `tests/test_api.py` y `tests/conftest.py`.
- Nota: las pruebas usan una base temporal o el `SQLITE_PATH` configurado; verificar que no apunten a datos reales.

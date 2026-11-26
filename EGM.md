# AI-T4 Blueprint

## System Overview

AI-T4 es el servicio FastAPI de MIDI, el componente inteligente del Centro de Especialidades Médicas Jehová Rafa. Recibe consultas del proxy PHP (`ControllerChat`), mantiene el estado clínico y la base de conocimiento en SQLite, y responde con la estructura `RespuestaOrientacion` que el frontend pinta en el chat.

El servicio usa un proveedor de IA con cadena de respaldo (Gemini, OpenCode, Groq, OpenAI o compatible). Para contexto clínico no consulta MySQL: llama por HTTP de solo lectura a `ControllerApi` con `X-API-Key` y, cuando corresponde, `X-Usuario-Id`.

Flujo actual:

1. El navegador envía la consulta a `Chat/preguntar` en PHP.
2. PHP agrega `X-API-Key`, `X-Usuario-Id`, `X-Usuario-Rol`, `X-Usuario-Nombre` y `peticion_id`, y llama a `POST /orientar`.
3. FastAPI abre o reutiliza una `consulta`, crea un `turno` idempotente, detecta dominio con la KB SQLite, hace preguntas, busca al paciente si hay cédula, carga controles/patologías y consulta el catálogo.
4. En el turno final, una unidad de trabajo escribe estado, mensaje, evidencia, validación (si aplica), cierre de consulta y outbox de auditoría.
5. El relay mueve el outbox a `auditoria`; la respuesta incluye `consulta_id`, `turno_id`, `mensaje_id` y `peticion_id`.
6. Un superusuario (`id_rol = 10`) revisa la cola de validación y las propuestas desde el módulo PHP `Validaciones`.

## Local Interface & Invariants

### Endpoints de `main.py`

- `GET /`: estado del servicio.
- `POST /orientar`: recibe `ConsultaIn` (`consulta`, `session_id`, `peticion_id`), exige `X-API-Key`, identifica al usuario por headers y devuelve la respuesta estructurada.
- `GET /sesiones/{session_id}` y `DELETE /sesiones/{session_id}`: consulta o borra una sesión.
- `GET /auditoria`: últimas filas de auditoría.
- `GET /validaciones` y `GET /validaciones/{id}`: cola y detalle de casos.
- `POST /validaciones/{id}/tomar`, `/decidir`, `/visto`: lease y decisión de un caso.
- `GET /propuestas`, `POST /propuestas`, `POST /propuestas/{id}/aprobar`, `/rechazar`: conocimiento propuesto.
- `GET /salud`: estado de SQLite, `foreign_key_check`, versión activa y pendientes.
- `GET /conocimiento` y `POST /conocimiento`: conocimiento aprendido y propuestas.
- `GET /memoria/similares` y `DELETE /memoria`: memoria vectorizada.

### Funciones internas relevantes

- `_datos_usuario(request)`: toma `id`, `rol` y `nombre` de headers; no los valida criptográficamente.
- `_extraer_cedula(texto)`: regex `\b([1-9][0-9]{6,7}(?:-R[0-9]{1,2})?)\b`.
- `_resolver_paciente(estado, texto, usuario)`: busca por cédula o nombre, elige la coincidencia exacta o el único resultado, y carga el contexto.
- `_cargar_contexto(estado, usuario)`: usa memoria por usuario/paciente; si no existe, consulta controles y patologías y guarda memoria.
- `_flujo_cuestionario`, `_flujo_general`, `_finalizar`, `_procesar`: máquina de estados del cuestionario y cierre.
- `_usuario_validacion(request)`: exige `X-Usuario-Id` y rol `10`/`superadmin` para la cola.

## Subdirectories & System Boundaries

- [Núcleo inteligente](./ai/EGM.md): cuestionario determinista, evidencia, confianza, embeddings, proveedores y esquema de respuesta.
- [Configuración](./config/EGM.md): `.env`, proveedores, SQLite, rutas del frontend.
- [Persistencia local](./storage/EGM.md): esquema SQLite, migraciones, KB, identidad, evidencia, validación, propuestas y auditoría.
- [Cliente PHP y herramientas](./tools/EGM.md): llamadas GET a `/Api/...`, catálogo cacheado y herramientas de solo lectura.
- [Despliegue](./deploy/EGM.md): instalador `systemd`, entorno virtual y unidad `midi.service`.
- `docs/`: documentación de diseño y diagramas; ver [índice del paquete](./docs/README.md).
- `knowledge/`: `dominios.json` y `aprendido.json` son **semilla de migración**; el runtime lee SQLite.
- `scripts/`: `seed_kb.py`, migración one-shot de la KB.
- `tests/`: pruebas; fuera del contrato por ser test-only.
- `data/`: base local heredada (`asistente.db`); no la referencia `config/settings.py`.

## Global Invariants

- **SQLite, no MariaDB.** El componente solo abre `storage/midi.db`. No hay conexión a MySQL ni escritura en la base clínica.
- **KB por tipo.** El runtime lee la KB activa desde `storage/conocimiento.py`; los JSON son semilla y respaldo de arranque.
- **Identidad consulta/turno.** Cada petición crea o reutiliza una `consulta` y un `turno`; `peticion_id` es la clave de idempotencia y una respuesta previa se reproduce sin volver a llamar al LLM.
- **Evidencia única.** Un `turno` tiene como máximo una `evidencia_turno`; la evidencia guarda hashes, versión de KB, componentes, candidatos y confianza.
- **Unidad de trabajo.** El cierre del turno escribe estado, mensaje, evidencia, validación, cierre y outbox en una sola transacción. Si falla, responde `503` reintentable.
- **Auditoría outbox.** La auditoría se escribe primero en `auditoria_outbox` y el relay la mueve a `auditoria` con `INSERT OR IGNORE` por `idempotency_key`.
- **Validación opcional.** La revisión no bloquea la respuesta. El caso nace `pendiente`, se toma con lease de 48 h y se decide con versión optimista. No hay autoaprobación de propuestas.
- **Confianza no gating.** Los seis componentes y sus pesos son fijos; la confianza decide revisión, no el tipo de respuesta. La muestra dorada es determinista al 5 % por `turno_id`.
- **API key compartida.** Los endpoints de negocio exigen `X-API-Key`; la clave debe coincidir con `API_KEY_IA` de CEMJR.
- **Herramientas de solo lectura.** `tools/php_client.py` solo hace GET a `/Api/...`; no crea pacientes, citas ni facturas.
- **JSON de compatibilidad.** `sesiones.estado_json`, `memorias.datos_json`, `memorias.embedding` y `auditoria.json_respuesta` siguen siendo el contrato del runtime; las tablas normalizadas son una sombra sincronizada por triggers.
- **Límites del flujo.** `MAX_HISTORIAL = 12`, `MAX_INTENTOS_PACIENTE = 1`, `MAX_PREGUNTAS_GENERAL = 5`. El cuestionario cierra al llegar a `min_preguntas` o `max_preguntas`.
- **Alarma primero.** Una señal de alarma positiva devuelve `emergencia` sin más preguntas ni botón.

## Global Side Effects

- Lectura/escritura de `storage/midi.db` (WAL, FKs, migraciones).
- Llamadas HTTP GET a PHP (`PHP_BASE_URL`).
- Llamadas a proveedores de IA y a Gemini para embeddings.
- Tareas de fondo: indexación de memoria y relay periódico de auditoría.
- Logs de consultas y errores; no se registra el texto crudo de la consulta en logs, solo longitud y hash.
- Sin escritura en MySQL, sin creación de pacientes desde FastAPI y sin correo.

## System Verification

- Run: `python -m pytest -q`
- Compilación: `python -m compileall main.py ai config storage tools scripts`
- Migración de KB: `python scripts/seed_kb.py` sobre una base temporal.
- Contratos: `ai/EGM.md`, `config/EGM.md`, `storage/EGM.md`, `tools/EGM.md`, `deploy/EGM.md`.
- Nota: el servicio requiere `.env`, API key y PHP disponible para las pruebas de integración. No ejecutar contra producción sin una copia controlada.

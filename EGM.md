# AI-T4 Blueprint

## System Overview

AI-T4 es el servicio FastAPI de MIDI, el asistente del Centro de Especialidades Médicas Jehová Rafa. Recibe consultas del proxy PHP (`ControllerChat`), mantiene sesiones y memoria en SQLite, y responde con una estructura `RespuestaOrientacion` que el frontend pinta en el chat.

El servicio usa un proveedor de IA con cadena de respaldo (Gemini, OpenCode, Groq, OpenAI o compatible). Para contexto clínico no consulta MySQL: llama por HTTP a los endpoints de solo lectura de `ControllerApi` con `X-API-Key` y, cuando corresponde, `X-Usuario-Id`.

Flujo observado:

1. El navegador envía la consulta a `Chat/preguntar` en PHP.
2. PHP agrega `X-API-Key`, `X-Usuario-Id`, `X-Usuario-Rol` y `X-Usuario-Nombre`, y llama a `POST /orientar`.
3. FastAPI detecta dominio, hace preguntas, busca al paciente si hay cédula, carga controles/patologías y consulta el catálogo de especialidades.
4. FastAPI devuelve `tipo_respuesta`, `mensaje`, especialidad, listas clínicas, módulo y `accion_sugerida`.
5. El navegador pinta la respuesta; el botón de acción abre una ruta del frontend PHP.

## Local Interface & Invariants

### Endpoints de `main.py`

- `GET /`: estado del servicio.
- `POST /orientar`: recibe `ConsultaIn` (`consulta`, `session_id`), exige `X-API-Key`, identifica al usuario por headers y devuelve la respuesta estructurada.
- `GET /sesiones/{session_id}`: consulta una sesión.
- `DELETE /sesiones/{session_id}`: borra una sesión.
- `GET /auditoria`: consulta auditoría.
- `GET /conocimiento` y `POST /conocimiento`: lee/agrega conocimiento aprendido.
- `GET /memoria/similares` y `DELETE /memoria`: consulta o borra memoria.

### Funciones internas relevantes

- `_datos_usuario(request)`: toma `id`, `rol` y `nombre` de headers; no los valida criptográficamente.
- `_extraer_cedula(texto)`: regex `\b(\d{6,10})\b`; **no acepta el sufijo `-R` de menores**.
- `_resolver_paciente(estado, texto, usuario)`: busca pacientes por cédula/nombre y carga el contexto.
- `_cargar_contexto(estado, usuario)`: consulta controles y patologías, guarda memoria y calcula embeddings.
- `_procesar`, `_flujo_cuestionario`, `_flujo_general`, `_finalizar`: flujo de preguntas y respuesta final.
- `verificar_api_key`: compara `X-API-Key` con `API_KEY_COMPARTIDA`.

### Invariants

- **API key compartida.** Todos los endpoints de negocio exigen `X-API-Key`; la clave debe coincidir con `API_KEY_IA` de CEMJR. En la revisión actual coincide.
- **Identidad por headers.** FastAPI toma `X-Usuario-Id`, `X-Usuario-Rol` y `X-Usuario-Nombre` del proxy. No hay sesión propia ni validación de rol en FastAPI; la autorización real está en PHP.
- **Lectura de PHP.** `tools/php_client.py` solo hace GET a `/Api/...`; no crea pacientes, citas ni facturas.
- **Memoria local.** Sesiones, memoria y auditoría viven en `storage/midi.db` (SQLite); no son la base clínica.
- **Respuesta estructurada.** `ai/schemas.py:RespuestaOrientacion` define los campos de salida; los flujos construyen diccionarios con esos campos.
- **Prompt.** `guia.md` define identidad, alcance, lenguaje, preguntas y tipos de respuesta; `ai/comun.py` y `ai/gemini.py` lo inyectan en el system prompt.
- **Herramientas.** `tools/clinica.py:TOOLS` expone `listar_doctores`, `mis_datos`, `buscar_paciente` y `datos_clinicos_paciente`; todas son de solo lectura.

## Subdirectories & System Boundaries

- [Cliente PHP y herramientas](./tools/EGM.md): llamadas GET a `/Api/...`, headers, catálogo cacheado y herramientas de solo lectura.
- [Configuración](./config/EGM.md): `.env`, `PHP_BASE_URL`, API key, proveedores de IA y rutas del frontend.
- `ai/`: proveedores de IA, prompts, cuestionario, embeddings y esquema `RespuestaOrientacion`. Sin `EGM.md` propio en esta pasada.
- `storage/`: SQLite de sesiones, memoria y auditoría. Sin `EGM.md` propio en esta pasada.
- `deploy/`: script de instalación del servicio. Sin `EGM.md` propio en esta pasada.
- `data/`, `knowledge/`: bases locales y catálogos de dominios/aprendizaje. Sin `EGM.md` propio en esta pasada.
- `tests/`: pruebas; fuera del contrato por ser test-only.

## Integración actual con CEMJR

| Uso | Endpoint PHP | Método | Headers |
|---|---|---|---|
| Catálogo de especialidades | `/Api/apiEspecialidades` | GET | `X-API-Key` |
| Doctores por especialidad | `/Api/apiDoctoresPorEspecialidad/{id}` | GET | `X-API-Key` |
| Datos del usuario logueado | `/Api/apiDatosUsuario/{id_usuario}` | GET | `X-API-Key` |
| Buscar paciente | `/Api/apiBuscarPaciente?q=...` | GET | `X-API-Key`, `X-Usuario-Id` |
| Controles del paciente | `/Api/apiControlesPaciente/{id_paciente}` | GET | `X-API-Key`, `X-Usuario-Id` |
| Patologías del paciente | `/Api/apiPatologiasPaciente/{id_paciente}` | GET | `X-API-Key`, `X-Usuario-Id` |

No hay llamadas a `Pacientes/guardar`, `Citas/mostrarHorario`, `Citas/validarHorariosDisponlibles` ni a ningún endpoint de escritura.

## Compatibilidad con las funciones propuestas

### Alta de pacientes desde el chatbot

**Estado actual:** no existe. `php_client` solo tiene GET; `ControllerApi` es de solo lectura; `ControllerPacientes::guardar` exige sesión, CSRF y `$_POST`. El chatbot no puede crear un paciente con el contrato actual.

**Ruta que no rompe lo existente:** el navegador de recepción confirma el borrador y llama a un endpoint PHP nuevo (`Pacientes/guardarDesdeChatbot`) con sesión y CSRF. FastAPI solo devuelve el borrador; no escribe. Para eso hay que:

- agregar un campo opcional de borrador a `RespuestaOrientacion` y a la respuesta de `/orientar`;
- enseñar a `guia.md` a pedir los campos y a no crear;
- agregar el manejo del borrador/confirmación en `chatModal.js`;
- crear el endpoint PHP con la validación de `ModeloPacientes`.

Un campo opcional no rompe a los clientes actuales; el frontend que no lo conozca lo ignora.

### Citas y disponibilidad

**Estado actual:** no existe consulta de disponibilidad. `config/modulos.py` solo genera rutas de frontend (`/Citas/citasHoy`); `php_client` no llama a `Citas/mostrarHorario` ni a `validarHorariosDisponlibles`. `ControllerApi` tampoco expone esos datos.

**Para que funcione sin romper:** agregar endpoints PHP de solo lectura para días/horas y cupos, protegerlos con la misma API key y `X-Usuario-Id`, y añadir métodos en `php_client`. El chatbot solo consulta; no reserva. La alternativa es que el navegador consulte `Citas` con su sesión y el chatbot solo ofrezca el enlace, pero entonces no hay disponibilidad real dentro del chat.

### Cédulas de menores

**Estado actual:** `_extraer_cedula` usa `\b(\d{6,10})\b`; con `12345678-R1` extrae `12345678` y busca al representante, no al menor. Eso puede devolver el paciente equivocado. Hay que aceptar el sufijo `-R[0-9]{1,2}` en `main.py` y en cualquier extracción de cédula del chatbot.

### URL base y configuración

- `config/settings.py` tiene un valor por defecto con el nombre antiguo del proyecto.
- El `.env` actual de AI-T4 usa `PHP_BASE_URL=https://127.0.0.1`.
- Hay que confirmar que esa URL sea la raíz real de CEMJR, que el TLS sea válido y que `/Api/...` responda. Si CEMJR está en `/repo/CEMJR` o en HTTP, las llamadas fallan.
- La clave `API_KEY_COMPARTIDA` de AI-T4 coincide con `API_KEY_IA` de CEMJR en la revisión actual.

### Prompt y autorización

`guia.md` no contiene instrucciones para registrar pacientes. El markdown puede limitar la conversación, pero no autoriza: el endpoint PHP debe comprobar sesión y permiso. Un doctor que llegue al endpoint no debe poder crear aunque el prompt diga que no.

## Global Side Effects

- Llamadas HTTP GET a PHP.
- Llamadas a proveedores de IA (Gemini/OpenCode/Groq/OpenAI/custom).
- Escritura/lectura en SQLite (`storage/midi.db`) para sesiones, memoria y auditoría.
- Embeddings y caché de catálogo.
- Logs de consultas y errores.
- Sin escritura en MySQL, sin archivos de pacientes y sin correo.

## System Verification

- Run: `pytest`
- Nota: el servicio requiere `.env`, API key y PHP disponible para las pruebas de integración. No ejecutar contra producción sin una copia controlada.

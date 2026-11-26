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
- `_extraer_cedula(texto)`: regex `\b([1-9][0-9]{6,7}(?:-R[0-9]{1,2})?)\b`; acepta cédulas de 7 u 8 dígitos y el sufijo `-R1`/`-R99` de menores.
- `_resolver_paciente(estado, texto, usuario)`: exige al menos 2 caracteres, busca por cédula o nombre, elige la coincidencia exacta de cédula o el único resultado, y carga el contexto. Si no hay resultados o hay ambigüedad, retorna sin avisar.
- `_cargar_contexto(estado, usuario)`: usa primero la memoria por usuario/paciente; si no existe, consulta controles y patologías en paralelo, guarda memoria y lanza el embedding en segundo plano.
- `_indexar_memoria(id_usuario, id_paciente, resumen)`: calcula el embedding y lo guarda; se ejecuta como tarea de fondo.
- `_respuesta_pregunta(texto, estado, progreso=None)`: construye una respuesta `aclaracion`. **Devuelve siempre el mismo `mensaje`: «Necesito un poco más de información para orientar mejor.»**; solo cambia `pregunta_activa`/`pregunta_aclaratoria`.
- `_respuesta_emergencia()`: construye una respuesta `emergencia` con progreso 100 y sin botón.
- `_accion(especialidad)`: construye el botón de cita o lo deja invisible.
- `_finalizar(estado, usuario)`: construye la ficha, llama al proveedor, fuerza `orientacion` salvo emergencia y completa especialidad, pruebas, asociaciones, hallazgos, recomendación y acción.
- `_flujo_cuestionario(consulta, estado, usuario)`: registra la respuesta pendiente, evalúa alarmas, identifica al paciente una vez, decide si hay información suficiente y devuelve la siguiente pregunta.
- `_flujo_general(consulta, historial, estado)`: flujo con LLM para síntomas fuera de los dominios; permite hasta 5 preguntas y luego cierra.
- `_cierre_general(consulta, historial, estado)`: fuerza el cierre sin más preguntas; si el modelo insiste en aclarar, usa `CONSULTA GENERAL` como respaldo.
- `_procesar(consulta, historial, estado, usuario)`: decide entre flujo de dominio y flujo general; si la sesión ya cerró, la reinicia; si el flujo general ya hizo preguntas, no cambia de dominio.
- `verificar_api_key`: compara `X-API-Key` con `API_KEY_COMPARTIDA`.

### Invariants

- **API key compartida.** Todos los endpoints de negocio exigen `X-API-Key`; la clave debe coincidir con `API_KEY_IA` de CEMJR.
- **Identidad por headers.** FastAPI toma `X-Usuario-Id`, `X-Usuario-Rol` y `X-Usuario-Nombre` del proxy. No hay sesión propia ni validación de rol en FastAPI; la autorización real está en PHP.
- **Lectura de PHP.** `tools/php_client.py` solo hace GET a `/Api/...`; no crea pacientes, citas ni facturas.
- **Memoria local.** Sesiones, memoria y auditoría viven en `storage/midi.db` (SQLite); no son la base clínica.
- **Respuesta estructurada.** `ai/schemas.py:RespuestaOrientacion` define los campos de salida; los flujos construyen diccionarios con esos campos.
- **Prompt.** `guia.md` define identidad, alcance, lenguaje, preguntas y tipos de respuesta; `ai/comun.py`, `ai/gemini.py` y `ai/openai_compatible.py` lo inyectan en el system prompt.
- **Herramientas.** `tools/clinica.py:TOOLS` expone `listar_doctores`, `mis_datos`, `buscar_paciente` y `datos_clinicos_paciente`; todas son de solo lectura.
- **Límites del flujo.** `MAX_HISTORIAL = 12`, `MAX_INTENTOS_PACIENTE = 1` y `MAX_PREGUNTAS_GENERAL = 5`. El cuestionario por dominio cierra al llegar a `min_preguntas` o a `max_preguntas`.
- **Una pregunta por turno.** `_flujo_cuestionario` registra como máximo la respuesta de `estado["siguiente_pregunta"]`; después limpia ese campo y devuelve una sola pregunta o la orientación final.
- **Alarma primero.** Si el motivo o cualquier respuesta contiene una señal de alarma del dominio, se devuelve `emergencia` sin más preguntas ni botón.
- **Paciente silencioso.** Si no hay paciente o hay varias coincidencias, `_resolver_paciente` retorna sin informar. `_flujo_cuestionario` pide la cédula una vez; si no se resuelve, marca `paciente_omitido` y continúa. La respuesta no declara si el paciente está registrado ni qué datos se usaron.
- **Mensaje de aclaración fijo.** `_respuesta_pregunta` devuelve siempre «Necesito un poco más de información para orientar mejor.» como `mensaje`, aunque la pregunta cambie. El flujo general no usa esa función; su mensaje lo redacta el LLM.
- **Especialidad de cierre.** `_finalizar` usa `especialidad_candidata` (primera especialidad del dominio presente en el catálogo; si ninguna coincide, intenta `CONSULTA GENERAL`; si tampoco está, `None`). Si el LLM devolvió una especialidad válida, se conserva. El tipo se fuerza a `orientacion` salvo `emergencia`.
- **Sin motivo de derivación.** La respuesta no incluye un campo que explique por qué se eligió la especialidad; `observacion` solo se usa para avisar que la especialidad del modelo no estaba en el catálogo.
- **Reinicio de sesión.** Si `estado["completo"]` es verdadero, `_procesar` limpia el estado y trata el mensaje como una consulta nueva. Si el flujo general ya hizo preguntas, no se cambia a un dominio a mitad de conversación.
- **Aprendizaje al detectar dominio.** `_procesar` llama a `cuestionario.aprender_ejemplo(dominio, consulta)` al iniciar un dominio nuevo; no hay aprobación humana ni borrado.
- **Auditoría.** Cada `POST /orientar` intenta registrar sesión, usuario, paciente, dominio, consulta, tipo, especialidad, pruebas, modelo, latencia y JSON de respuesta. La auditoría es append-only; un fallo al registrar se loguea y no interrumpe la respuesta.

## Subdirectories & System Boundaries

- [Cliente PHP y herramientas](./tools/EGM.md): llamadas GET a `/Api/...`, headers, catálogo cacheado y herramientas de solo lectura.
- [Configuración](./config/EGM.md): `.env`, `PHP_BASE_URL`, API key, proveedores de IA y rutas del frontend.
- [Núcleo inteligente](./ai/EGM.md): proveedores de IA, prompt, cuestionario, aprendizaje, embeddings y esquema `RespuestaOrientacion`.
- [Persistencia local](./storage/EGM.md): SQLite de sesiones, mensajes, memoria y auditoría.
- [Despliegue](./deploy/EGM.md): instalador `systemd`, entorno virtual, permisos y unidad `midi.service`.
- `docs/`: documentación de diseño y diagramas; ver [índice del paquete](./docs/README.md). No es un contrato de código.
- `knowledge/`: `dominios.json` (curado) y `aprendido.json` (runtime). Es dato, no código; se documenta en `ai/EGM.md` y en el diseño de la base de conocimiento.
- `data/`: base local heredada (`asistente.db`); no la referencia `config/settings.py`. La base activa es `storage/midi.db`.
- `tests/`: pruebas; fuera del contrato por ser test-only.

## Documentación de diseño

- [Índice del paquete de diagramas](./docs/README.md)
- [Diagrama general de casos de uso del sistema](./docs/01-diagrama-general-caso-sistema.md)
- [Caso de uso solo del componente MIDI](./docs/04-caso-uso-componente.md)
- [Arquitectura del componente inteligente](./docs/02-arquitectura-componente-inteligente.md)
- [Base de conocimiento: tablas y relaciones](./docs/03-base-de-conocimiento-relacional.md)

Los documentos de `docs/` describen el sistema actual y separan explícitamente lo implementado de lo propuesto. No sustituyen a los contratos `EGM.md` de cada directorio.

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

## Compatibilidad y brechas actuales

### Alta de pacientes desde el chatbot

**Estado actual:** el borrador ya existe en el contrato y en el prompt. `RespuestaOrientacion.paciente_borrador` y el tipo `registro_paciente` están en `ai/schemas.py`; `guia.md` y `ai/comun.py:system_prompt` piden los datos y prohíben crear. FastAPI no escribe: `php_client` solo hace GET y `ControllerApi` es de solo lectura. Falta el endpoint PHP que confirme el alta y el manejo del borrador en `chatModal.js`.

**Ruta que no rompe lo existente:** el navegador de recepción confirma el borrador y llama a un endpoint PHP nuevo (`Pacientes/guardarDesdeChatbot`) con sesión y CSRF. FastAPI solo devuelve el borrador. La autorización real debe quedar en PHP.

### Citas y disponibilidad

**Estado actual:** no existe consulta de disponibilidad. `config/modulos.py` solo genera rutas de frontend (`/Citas/citasHoy`); `php_client` no llama a `Citas/mostrarHorario` ni a `validarHorariosDisponlibles`. `ControllerApi` tampoco expone esos datos.

**Para que funcione sin romper:** agregar endpoints PHP de solo lectura para días/horas y cupos, protegerlos con la misma API key y `X-Usuario-Id`, y añadir métodos en `php_client`. El chatbot solo consulta; no reserva. La alternativa es que el navegador consulte `Citas` con su sesión y el chatbot solo ofrezca el enlace, pero entonces no hay disponibilidad real dentro del chat.

### Cédulas de menores

**Estado actual:** `_extraer_cedula` acepta `\b([1-9][0-9]{6,7}(?:-R[0-9]{1,2})?)\b`: cédulas de 7 u 8 dígitos y el sufijo `-R1`/`-R99`. Ya no recorta el sufijo. El riesgo restante es que el patrón también puede coincidir con números de 7-8 dígitos que no sean cédulas (teléfonos, códigos); la búsqueda en PHP debe confirmar la coincidencia.

### URL base y configuración

- `config/settings.py` tiene un valor por defecto con el nombre antiguo del proyecto.
- Hay que confirmar que `PHP_BASE_URL` del `.env` sea la raíz real de CEMJR, que el TLS sea válido y que `/Api/...` responda. Si CEMJR está en un subdirectorio o por HTTP, las llamadas fallan.
- `API_KEY_COMPARTIDA` de AI-T4 y `API_KEY_IA` de CEMJR deben ser iguales.

### Prompt y autorización

`guia.md` y `ai/comun.py:system_prompt` ya contienen instrucciones para preparar el borrador de paciente y para no crear. El markdown puede limitar la conversación, pero no autoriza: el endpoint PHP debe comprobar sesión y permiso. Un doctor que llegue al endpoint no debe poder crear aunque el prompt diga que no.

## Brechas y cambios propuestos (no implementados)

> **Estado:** propuesta de diseño. Las brechas **B-01 a B-07** no están implementadas en el código actual; **B-08** está documentada en `docs/04`. Se separa lo que existe de lo que se quiere cambiar para que el brief no atribuya al sistema funciones que todavía no tiene.

| ID | Brecha observada | Evidencia actual | Cambio propuesto | Estado |
|---|---|---|---|---|
| **B-01** | La misma frase «Necesito más información» en cada aclaración. | `main.py:_respuesta_pregunta` devuelve un `mensaje` fijo. | Mensaje contextual por pregunta; prueba que detecte repetición consecutiva. | Pendiente |
| **B-02** | No se informa si el paciente está registrado ni qué datos se usan. | `_resolver_paciente` retorna en silencio; `paciente_omitido` no se comunica. | Campos de estado del paciente, datos usados y acción de registro. | Pendiente |
| **B-03** | No hay gastroenterología ni motivo de derivación; general no es «última opción». | `dolor_abdominal` solo tiene `CONSULTA GENERAL`; `especialidad_candidata` cae a general sin marca de último recurso. | Prioridad explícita, especialidad clínica validada y `motivo_derivacion`. | Pendiente |
| **B-04** | El aprendizaje no se revisa y no aprende relaciones con especialidades. | `aprender_ejemplo` se llama automáticamente; no hay aprobación ni borrado. | Aprendizaje gobernado por médico/administrador, con origen y auditoría. | Pendiente |
| **B-05** | Los dominios siguen en JSON; el modelo relacional es solo una propuesta. | `ai/cuestionario.py` lee `dominios.json`; `docs/03` propone tablas. | Decidir si SQLite normalizado es fuente de verdad o copia operativa. | Pendiente |
| **B-06** | No hay interfaz para crear dominios. | `POST /conocimiento` solo agrega ejemplos/palabras a dominios existentes. | CRUD administrativo con validación, roles y auditoría. | Pendiente |
| **B-07** | No hay mecanismo definido de injerencia humana. | Solo existen `GET /auditoria`, `GET/POST /conocimiento` y `DELETE /memoria`. | Definir quién corrige, aprueba o interviene y cómo se registra. | Pendiente |
| **B-08** | El diagrama de casos de uso general no aísla el componente. | `docs/01` incluye el sistema CEM completo. | Nuevo diagrama solo del componente en `docs/04`. | Documentado |

### B-01 — Mensaje de aclaración repetido

**Causa verificada:** `main.py:_respuesta_pregunta` construye todas las respuestas `aclaracion` con el mismo `mensaje`; solo cambia `pregunta_activa`. La misma función se usa para pedir la cédula y para cada pregunta del dominio. En el flujo general el mensaje lo genera el LLM y `guia.md` no prohíbe repetir la muletilla.

**Propuesta:** eliminar el mensaje fijo; usar un texto breve que introduzca la pregunta concreta, o devolver la pregunta como `mensaje` y mantener `pregunta_activa` para el frontend. Añadir una prueba que compare dos aclaraciones consecutivas y falle si el texto es idéntico. No se propone cambiar el modelo: el problema del flujo determinista es de código.

### B-02 — Estado del paciente y datos usados

**Comportamiento actual:** `_resolver_paciente` devuelve sin avisar si no hay resultados o si hay más de una coincidencia. `_flujo_cuestionario` pide la cédula una vez; si no se resuelve, marca `paciente_omitido` y sigue. `construir_ficha` escribe «Paciente: No identificado» si no hay nombre. La respuesta al usuario no dice si el paciente está registrado, si se omitió la búsqueda ni qué información se consultó.

**Propuesta:** agregar a la respuesta campos explícitos, por ejemplo `paciente_estado` (`registrado`, `no_registrado`, `ambiguo`, `omitido`), `paciente_mensaje` y `datos_usados` (cédula, nombre, controles de los últimos 6 meses, patologías, medicamentos de controles previos). Si no está registrado, ofrecer la acción de registro o indicar a recepción que lo registre. Falta decidir si el flujo se detiene hasta registrarlo o continúa sin antecedentes; hoy continúa. La declaración de datos usados debe ser breve y no volcar el historial completo en el chat.

### B-03 — Especialidad, gastroenterología y motivo

**Comportamiento actual:** `knowledge/dominios.json` no contiene `GASTROENTEROLOGIA`. `dolor_abdominal` solo declara `CONSULTA GENERAL`. `especialidad_candidata` devuelve la primera especialidad de la lista que exista en el catálogo; si ninguna coincide, intenta `CONSULTA GENERAL`; si tampoco está, devuelve `None`. No hay una marca de «último recurso» ni una explicación de por qué se eligió la especialidad. `_finalizar` puede conservar una especialidad válida devuelta por el LLM aunque no esté en la lista del dominio.

**Propuesta:** separar la especialidad clínica de la de respaldo. Agregar a cada dominio una lista ordenada con `prioridad` y `ultimo_recurso`; `CONSULTA GENERAL` solo se usa si no hay candidata clínica o si el usuario pide medicina general. Si la especialidad clínica no existe en el catálogo real, degradar a `derivar` o `catalogo`, no a general en silencio. Agregar `GASTROENTEROLOGIA` para los hallazgos abdominales que correspondan, solo después de confirmar que existe en `/Api/apiEspecialidades`. Añadir `motivo_derivacion` y, si se puede, `evidencia` (pregunta/respuesta o regla) calculados en Python; el LLM no debe inventar la justificación. Guardar ambos en auditoría.

**Aprendizaje asociado:** la relación «este caso va a gastroenterología» solo debe aprenderse si un médico o administrador la confirma. Aprender de la propia salida del sistema refuerza errores y no tiene verdad de referencia.

### B-04 — Aprendizaje gobernado

**Comportamiento actual:** `main.py` llama a `cuestionario.aprender_ejemplo` al iniciar un dominio. `aprender_ejemplo` deduplica, limita a 50 ejemplos y escribe `knowledge/aprendido.json`; no hay aprobación, caducidad, borrado ni origen. `POST /conocimiento` agrega ejemplos o palabras, pero no permite eliminar. El aprendizaje solo mejora la detección de dominio; no aprende especialidades, motivos ni correcciones.

**Propuesta:** agregar un flujo de revisión: el sistema propone un ejemplo o una relación, un médico/administrador la aprueba o la rechaza, y solo entonces se incorpora. Guardar origen (`conversacion`, `manual`, `correccion_medica`), fecha, autor, dominio y especialidad sugerida. Permitir borrar y desactivar. Auditar cada cambio. No aprender automáticamente de la respuesta del propio sistema.

### B-05 — Dominios en más tablas y SQLite

**Comportamiento actual:** el conocimiento curado vive en `knowledge/dominios.json` y lo aprendido en `knowledge/aprendido.json`. `ai/cuestionario.py:dominios()` los fusiona en memoria. `docs/03` ya contiene un modelo relacional normalizado (`dominio`, `dominio_palabra_clave`, `dominio_senal_alarma`, `dominio_especialidad`, `dominio_prueba`, `dominio_asociacion`, `dominio_descartar`, `pregunta`, `ejemplo_aprendido`, `catalogo_especialidad`), pero ese DDL no se ejecuta. SQLite se usa hoy solo para sesiones, mensajes, memoria y auditoría.

**Propuesta:** decidir explícitamente entre dos rutas:

1. **SQLite como fuente de verdad:** crear las tablas normalizadas, sembrarlas desde los JSON y exponer CRUD administrativo. Ventaja: consultas e integridad. Coste: pierde la revisión por diff de Git y exige migraciones, respaldo y control de concurrencia.
2. **JSON como fuente de verdad:** mantener `dominios.json` versionado y usar SQLite solo como copia operativa o caché de lectura. Ventaja: revisión y rollback simples. Coste: no hay integridad referencial ni consultas relacionales directas.

`aiosqlite` es un envoltorio async de `sqlite3`, no otro motor; migrar la KB a SQLite no cambia el archivo ni el formato de la base. La decisión debe quedar escrita antes de tocar `ai/cuestionario.py`.

### B-06 — Interfaz para agregar dominios

**Comportamiento actual:** `POST /conocimiento` recibe `dominio`, `ejemplo` y `palabras_clave`; si el dominio no existe, devuelve 404. No crea dominios, no edita preguntas, señales, especialidades ni pruebas, y no tiene interfaz gráfica. La única protección es `X-API-Key`; no hay rol ni auditoría del cambio.

**Propuesta:** una interfaz administrativa para crear y editar dominios completos, con validación (clave única, `min_preguntas ≤ max_preguntas`, especialidades existentes en el catálogo, preguntas con id único), vista previa, confirmación y auditoría. Debe exigir rol de administrador, no solo la API key. Si la fuente de verdad sigue siendo JSON, la interfaz debe escribir a través de un flujo revisado, no directo al archivo en caliente.

### B-07 — Mecanismo de interacción para injerencia

**Estado actual:** no existe. El administrador puede consultar auditoría, agregar conocimiento y borrar memoria; no puede corregir una derivación, aprobar un aprendizaje ni intervenir en una conversación. El médico no tiene un canal de corrección dentro de MIDI.

**Propuesta pendiente de definición:** distinguir al menos tres formas de injerencia:

- **Corrección posterior:** el médico o administrador marca una consulta auditada como mal derivada y deja la especialidad correcta; eso alimenta el aprendizaje gobernado.
- **Aprobación previa:** el administrador revisa ejemplos y relaciones antes de que se usen.
- **Intervención en vivo:** una persona toma la conversación o corrige la respuesta antes de que llegue al paciente; esto exige un canal y una UI que hoy no existen.

No se debe implementar «injerencia» sin decidir cuál de las tres se necesita. La opción de corrección posterior es la de menor coste y la que mejor encaja con la auditoría actual.

### B-08 — Caso de uso solo del componente

**Estado:** documentado en [`docs/04-caso-uso-componente.md`](./docs/04-caso-uso-componente.md). El diagrama aísla la frontera de MIDI: muestra los casos internos y los sistemas externos (PHP, proveedores de IA, SQLite y archivos de conocimiento), sin la frontera del sistema CEM completo. `docs/01` se mantiene como vista general del sistema.

## Global Side Effects

- Llamadas HTTP GET a PHP.
- Llamadas a proveedores de IA (Gemini/OpenCode/Groq/OpenAI/custom).
- Escritura/lectura en SQLite (`storage/midi.db`) para sesiones, memoria y auditoría.
- Escritura de `knowledge/aprendido.json` cuando se detecta un dominio o se agrega conocimiento.
- Embeddings, caché de catálogo y tareas de fondo para indexar memoria.
- Logs de consultas y errores.
- Sin escritura en MySQL, sin creación de pacientes desde FastAPI y sin correo.

## System Verification

- Run: `pytest`
- Contratos: `ai/EGM.md`, `config/EGM.md`, `storage/EGM.md`, `tools/EGM.md`, `deploy/EGM.md`.
- Nota: el servicio requiere `.env`, API key y PHP disponible para las pruebas de integración. No ejecutar contra producción sin una copia controlada.

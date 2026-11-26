# Revisión clínica posterior y base de conocimiento relacional de MIDI

* **Author:** Juanxrpana
* **Date:** 2026-11-26

## Overview

MIDI seguirá recomendando una especialidad, no obligando al paciente a agendar. La validación del especialista será posterior y opcional: sirve para control de calidad y aprendizaje, no como compuerta. La base de conocimiento clínica dejará de vivir en `knowledge/dominios.json` y `knowledge/aprendido.json` y pasará a SQLite relacional, con `dominio` como raíz y claves foráneas reales hacia palabras, señales, preguntas, especialidades, pruebas, asociaciones y hallazgos.

La propuesta añade dos piezas que hoy no existen: un índice determinista de confianza que marque casos dudosos o multi-dominio, y un registro de validaciones con la ficha, la respuesta final, el motivo de la corrección y las propuestas de palabras o preguntas. `mensajes`, `sesiones`, `memorias` y `auditoria` se conservan; las tablas nuevas son complementarias, no reemplazos.

## Analysis

### Revisión realizada

| Lente | Resultado |
|---|---|
| Design Critic | completado |
| Codebase Details | completado |
| Zoom Out / YAGNI | completado |
| UX & Ergonomics | completado |
| Migration & Compatibility | completado |
| Structural / Tech Debt | completado |
| Inventive Catalyst | completado |

Los siete revisores coinciden en tres puntos: el diseño no tiene identidad de consulta/turno, las claves foráneas propuestas no se aplicarían hoy, y la validación posterior no mejora la respuesta que ya recibió el paciente. Las diferencias están en cuánto normalizar y cuánto construir ahora.

### 1. La contradicción principal: «sin JSON» contra las columnas JSON existentes

El autor pidió eliminar JSON y pasar a «pura base de datos relacional». Eso es claro para los archivos de conocimiento: `knowledge/dominios.json` y `knowledge/aprendido.json` desaparecen como fuente de verdad. No es claro para las columnas operativas:

- `sesiones.estado_json` es la máquina de estados del cuestionario (`storage/db.py`, `storage/sesiones.py`).
- `memorias.datos_json` es un payload clínico que pertenece a PHP (`storage/memoria.py`).
- `memorias.embedding` es un vector; normalizarlo a una fila por dimensión no es un modelo relacional útil.
- `auditoria.json_respuesta` es la evidencia de lo que el usuario recibió (`storage/auditoria.py`).

Eliminar esas columnas en la misma fase no es añadir tablas complementarias: es reescribir `main.py`, `storage/sesiones.py`, `storage/memoria.py`, `storage/auditoria.py` y parte de `ai/schemas.py`. Los revisores lo marcan como blocker de alcance, no como detalle de implementación.

La distinción que sí se sostiene es: **ningún conocimiento clínico se lee desde JSON**. El conocimiento curado y aprendido pasa a tablas con FK. Las columnas operativas que son instantáneas, vectores o contratos externos se tratan como datos opacos versionados, con una excepción documentada y una retención definida. **Decisión aceptada:** la fase 1 elimina los archivos JSON de conocimiento; la fase 2 normaliza las columnas operativas una por una. Si más adelante se exige pureza total, se costea como una segunda migración, no se esconde dentro de la primera.

### 2. Falta identidad de consulta y de turno

Hoy `session_id` se reutiliza para varias consultas: `_procesar` limpia el estado cuando `completo` y empieza otra consulta con el mismo identificador (`main.py`). `mensajes` no tiene `consulta_id` ni `turno_id`; `agregar_mensaje` devuelve `None`; `auditoria` no tiene `mensaje_id`; y la ficha se construye en una variable local que no se guarda (`main.py:_finalizar`). Por eso una corrección del doctor no se puede unir de forma fiable con la ficha, la respuesta, el mensaje y la auditoría de la consulta exacta.

La base necesita una entidad `consulta` y un `turno`:

- `consulta`: una episodio clínico dentro de una sesión, con `session_id`, usuario, paciente, flujo (`cuestionario`, `general`, `emergencia`), dominio nullable, inicio y cierre.
- `turno`: una petición y su respuesta dentro de la consulta, con secuencia, tipo de respuesta, origen (`llm`, `regla`, `fallback`), estado y fecha.
- `mensajes` conserva el texto, pero recibe `consulta_id` y `turno_id`; `agregar_mensaje` devuelve `lastrowid`.
- La evidencia de la ficha, la respuesta, la confianza y las versiones se enlaza al `turno`, no a una heurística de `session_id` + fecha.

Sin esto, la validación, la auditoría y el aprendizaje quedan colgados de identificadores ambiguos. Es el blocker más repetido por los revisores.

### 3. Las claves foráneas propuestas no se aplicarían

`PRAGMA foreign_keys=ON` es por conexión. `storage/db.py:init_db` configura una conexión, pero cada repositorio abre una nueva con `aiosqlite.connect(DB_PATH)` en `storage/sesiones.py`, `storage/memoria.py` y `storage/auditoria.py`. La base actual responde `PRAGMA foreign_keys = 0`. Declarar FKs sin una fábrica de conexiones que active el pragma no garantiza nada.

Además, SQLite no permite añadir una FK a una tabla existente con `ALTER TABLE`. `mensajes`, `auditoria` y `sesiones` ya tienen datos (90 mensajes, 45 auditorías, 10 sesiones, 1 memoria). Poner FKs reales exige reconstruir tablas con el procedimiento de renombrar, crear, copiar, verificar y borrar, dentro de una migración versionada.

El modelo de integridad debe separar dos planos:

- **Plano de conocimiento:** FKs duras entre `dominio` y sus tablas hijas. `dominio` se desactiva con `activo=0`, no se borra.
- **Plano de evidencia:** auditoría, validaciones y mensajes son registros históricos. No deben tener una FK que impida borrar una sesión ni una FK que borre la evidencia en cascada. Llevan una instantánea del dominio y de la especialidad, y referencias nullable cuando corresponda.

Hay 30 de 45 auditorías con `dominio IS NULL` porque el flujo general no tiene dominio. Un FK obligatorio a `dominio` en todas las tablas de caso es falso: no puede representar el flujo general ni la emergencia. `dominio_id` debe ser nullable en la consulta y en la evidencia, con `tipo_flujo` y `motivo_sin_dominio`.

La especialidad del catálogo tampoco es una buena FK por nombre. El catálogo es una caché en memoria de 600 segundos que puede estar vacía al arrancar. `CARDIOLOGIA` y `Cardiología` no son iguales para SQLite. La FK debe usar un `id_categoria` inmutable y guardar el nombre como instantánea; la sincronización con PHP debe ser upsert y desactivar, nunca borrar filas referenciadas.

### 4. El índice de confianza no tiene clasificador todavía

El diseño pide fuerza de palabra clave, margen entre el primero y el segundo, número de dominios candidatos y preguntas respondidas. Hoy `ai/cuestionario.py:detectar_dominio` devuelve el primer dominio que coincide por subcadena o el mejor ejemplo por Jaccard, sin puntajes, sin top-k y sin margen. `hay_alarma` usa la misma lógica de subcadena.

Eso produce falsos positivos con negación: «no tengo fiebre» coincide con `fiebre`; «sin dolor de pecho» coincide con `pecho`; «no tengo dificultad para respirar» puede disparar una alarma. Un índice construido sobre esa señal daría confianza alta precisamente a los falsos positivos seguros.

La recomendación es separar extracción de evidencia y puntaje:

- `detectar_candidatos(texto)` devuelve todos los dominios activos con puntaje, posición, término que coincidió y fuente (`palabra`, `ejemplo`, `llm`).
- El puntaje usa límites de palabra, polaridad/negación, longitud de la frase y especificidad del término.
- Se guarda `score_total`, cada componente, `detector_version`, `umbral_version` y los ids de las palabras o ejemplos que aportaron.
- El desempate debe ser determinista y explícito; no puede depender del orden de las filas de SQLite.
- La confianza clínica se separa de la salud operativa. Que PHP no tenga catálogo no es incertidumbre clínica; es un estado degradado que debe generar un aviso operativo y una respuesta de respaldo.

Con 45 auditorías y 4 dominios no hay datos para calibrar umbrales. Se puede empezar con un umbral provisional, pero debe marcarse como tal y ajustarse con las validaciones. La confianza del LLM, si se añade, se guarda como señal secundaria con proveedor y modelo; no decide sola el flag.

### 5. La validación opcional necesita dueño y cola

La validación posterior y opcional es coherente con «el paciente es recomendado, no obligado». El problema operativo es que nadie está obligado a revisar. Sin dueño, la cola queda vacía y el aprendizaje no recibe correcciones. Enrutar por la especialidad sugerida tiene un sesgo de confirmación: si la sugerencia es el error, el especialista equivocado revisa el caso y el correcto nunca lo ve.

**Decisión aceptada:** el especialista de la especialidad es el revisor natural. Si no valida, la cola pasa a administración. En esta fase solo el **super usuario** puede validar; el usuario que atiende queda para una fase posterior. El rol debe verificarse en PHP y no confiarse solo desde `X-Usuario-Rol`.

Hace falta:

- roles explícitos (`recepcion`, `doctor`, `admin_super_usuario`, `usuario_que_atiende`) verificados en PHP, no solo `X-API-Key` y headers de rol confiados;
- una cola con estados (`pendiente`, `asignada`, `vista`, `validada`, `corregida`, `descartada`, `expirada`), dueño, edad, filtros y paginación;
- un revisor natural (especialista de la especialidad) con respaldo de administración; en esta fase el respaldo es solo el super usuario;
- muestreo de casos de alta confianza como control, porque la confianza mide clasificación, no riesgo clínico;
- registro de quién vio la ficha y quién decidió, con retención y acceso auditados;
- una regla explícita de qué pasa si nadie revisa: el super usuario puede tomar el caso, o el caso expira con métrica.

La revisión opcional no puede ser la única barrera de seguridad. Si el objetivo es evitar que una mala orientación llegue al paciente, la validación tendría que ser previa al envío. Si el objetivo es aprendizaje y control de calidad, la revisión posterior es suficiente, pero debe decirse así.

### 6. La evidencia debe ser reproducible y la ficha no debe duplicarse sin control

La ficha que recibe el LLM no se guarda. Contiene nombre del paciente, motivo, respuestas, hasta cinco controles con diagnósticos y medicamentos, y recuerdos. Guardarla completa en cada mensaje duplica datos clínicos y aumenta el riesgo de privacidad. Reenviar toda la conversación a la cola de revisión tampoco es viable: puede haber demasiados mensajes y el costo de tokens crece sin necesidad.

**Decisión aceptada:** la evidencia guarda un **resumen estructurado** de la ficha y la respuesta final, no la conversación completa. El detalle de los mensajes sigue en `mensajes` para trazabilidad, pero la cola no lo reenvía ni lo muestra por defecto. El resumen incluye motivo, respuestas, antecedentes relevantes, dominio detectado, especialidad, confianza y resultado. Si el resumen se genera con el LLM, se genera una vez y se almacena; no se recalcula en cada revisión.

La evidencia debe incluir:

- `consulta_id`, `turno_id`, `mensaje_id`;
- `resumen_ficha` estructurado y `ficha_hash` del texto original que recibió el LLM;
- `respuesta_final` y su hash;
- `kb_version`, `prompt_version` o hash de `guia.md`, `modelo_usado`, `catalogo_snapshot_id`;
- dominio detectado, top-k candidatos y componentes de confianza;
- origen de la respuesta (`llm`, `fallback`, `regla`) y estado degradado.

No se guarda el prompt crudo ni el historial completo para la revisión. El vínculo a `mensajes` permite reconstruir el detalle si hay una disputa o una auditoría autorizada. La retención y el borrado deben definirse por tabla: una validación puede sobrevivir a la sesión, pero no debe conservar PII innecesaria.

### 7. El aprendizaje sigue sin pasar por aprobación

Hoy `main.py:_procesar` llama a `aprender_ejemplo` en cada detección de dominio. `POST /conocimiento` escribe ejemplos y palabras de inmediato. El nuevo diseño dice que la promoción requiere aprobación, pero esas dos rutas la saltan. Si los cuatro ejemplos de `knowledge/aprendido.json` se importan como aprobados, el gate nace vencido.

La propuesta debe separar:

- **observación:** frase detectada, sin efecto en la detección;
- **propuesta:** palabra, pregunta, relación o dominio nuevo, con origen, autor, motivo y evidencia;
- **aprobación:** un actor distinto del proponente, con transición de estado y auditoría;
- **publicación:** la fila aprobada entra en la versión activa de la KB.

Las propuestas del LLM a partir del motivo de corrección deben generarse bajo demanda, con límite de palabras y preguntas, y quedar pendientes. El LLM no debe proponer preguntas clínicas sin revisión. Hay que añadir una capa de error (`deteccion_dominio`, `mapeo_especialidad`, `preguntas`, `redaccion`, `datos_paciente`) y el dominio objetivo; si el error es de dominio, las palabras no deben proponerse para el dominio equivocado.

Además, hoy `dominios()` solo fusiona palabras y ejemplos aprendidos; no fusiona preguntas. Aprobar una pregunta no cambia el cuestionario. El cargador de conocimiento debe incluir preguntas aprobadas, con orden, estado y versión, y una prueba que demuestre que la pregunta se formula después de aprobarla.

### 8. Modelo relacional recomendado, sin reemplazar tablas

La forma mínima que satisface la petición y las revisiones:

| Tabla | Papel | Integridad |
|---|---|---|
| `dominio` | Raíz del conocimiento: clave, nombre, orden, activo, min/max. | PK; clave inmutable; soft delete. |
| `dominio_elemento` | Todo lo que cuelga de un dominio: palabra, señal, pregunta, especialidad, prueba, asociación, hallazgo o ejemplo. | FK a `dominio`; `tipo` con CHECK; `clave`, `valor`, `valor_normalizado`, `orden`, `activo`, `origen`, `estado`; `catalogo_id` nullable con FK. |
| `catalogo_especialidad` | Catálogo local por `id_categoria` y nombre. | Snapshot/upsert; no borrar referenciados. |
| `consulta` | Episodio clínico dentro de una sesión. | FK lógica a sesión; `dominio_id` nullable. |
| `turno` | Petición/respuesta dentro de la consulta. | FK a `consulta`; secuencia única. |
| `evidencia_turno` | Ficha, respuesta, hashes y versiones. | FK a `turno`; una fila por turno final. |
| `consulta_dominio_candidato` | Top-k con puntaje y evidencia. | FK a `turno` y `dominio`; rank único. |
| `validacion` | Corrección del doctor. | FK a `consulta` y `evidencia_turno`; dominio original/corregido nullable. |
| `validacion_evento` | Historial append-only de estados. | FK a `validacion`; sin updates destructivos. |
| `propuesta_conocimiento` | Palabra, pregunta, relación o dominio nuevo. | `dominio_id` nullable en staging; aprobación explícita. |
| `kb_version` / `schema_migrations` | Versión de conocimiento y esquema. | Sin FK; control de despliegue. |

No hace falta un segundo `mensajes` ni un segundo `auditoria`. Se conservan y se les añade `consulta_id`, `turno_id` y devolución de `lastrowid`. Las listas de candidatos y propuestas no se guardan como JSON si se quiere cumplir «sin JSON»; van a tablas hijas.

**Decisión aceptada:** las listas del dominio se guardan en una sola tabla `dominio_elemento`, no en ocho tablas separadas. `tipo` acepta `palabra_clave`, `senal_alarma`, `pregunta`, `especialidad`, `prueba`, `asociacion`, `descartar` y `ejemplo`. `clave` se usa para la identidad de una pregunta; `valor` guarda el texto; `valor_normalizado` se usa para comparar; `catalogo_id` solo aplica a especialidades; `origen` y `estado` distinguen curado, aprendido y pendiente. La unicidad es por `(dominio_id, tipo, valor_normalizado)` y por `(dominio_id, tipo, clave)` cuando `clave` no es nula. El orden se guarda en `orden` y se ordena por `(orden, id)`, sin `UNIQUE` de orden para no romper los intercambios.

El coste de la tabla única es que pierde restricciones específicas por tipo; se compensan con `CHECK` de `tipo`, validación en la aplicación y pruebas. La ventaja es una sola FK visible a `dominio`, un solo cargador y un diagrama entidad-relación directo, que es lo que pidió el profesor.

### 9. Migración y despliegue

La migración es el mayor riesgo técnico:

- `init_db` solo hace `CREATE TABLE IF NOT EXISTS`; no hay versión de esquema ni ledger de migraciones.
- Las tablas existentes con datos necesitan reconstrucción para FKs reales.
- Hay 39 palabras clave curadas que se reducen a 29 al normalizar; los duplicados incluyen `toracico/torácico`, `presion/presión`, `escalofrios/escalofríos`, `colico/cólico`, `picazon/picazón`. Hay que decidir si se conservan como alias o se deduplican, y reportar cada pérdida.
- Los cuatro ejemplos aprendidos no tienen fecha ni estado. Deben importarse como `pendiente`, no como aprobados.
- `storage/*.db` está en `.gitignore`; si la KB solo vive ahí y se pierde la base, la instalación arranca con cero dominios y todo cae al flujo general.
- El DDL de `docs/03` es MySQL (`AUTO_INCREMENT`), no SQLite; copiarlo falla.

La secuencia segura es: backup, migración versionada, seed desde los JSON actuales, verificación de conteos y `foreign_key_check`, arranque fail-closed si no hay dominios, y rollback probado. Mantener una exportación JSON por una versión para revisión y recuperación no contradice «no JSON en runtime»; es una red de seguridad de despliegue.

### 10. Observabilidad y operación

El estado actual no permite triage: `GET /` devuelve `{"estado":"ok"}`, `GET /auditoria` no filtra, y los logs no tienen `consulta_id`. Con la validación y la confianza, hacen falta:

- `consulta_id` en cada línea de log y en cada tabla de evidencia;
- salud con esquema, versión de KB, `foreign_keys`, `foreign_key_check`, catálogo, última auditoría y cola pendiente;
- métricas de dominio nulo, bandas de confianza, correcciones por motivo, fallback, auditorías fallidas, turnos incompletos y latencia por etapa;
- flag de respuesta degradada separado de la confianza clínica;
- registro de acceso a fichas y validaciones.

### 11. UX de la revisión

El doctor necesita una cola, no una tabla. **Decisión aceptada:** la cola y la pantalla de validación viven en el sistema PHP existente; FastAPI expone los endpoints de consulta y decisión. La recepción no debería ver un porcentaje crudo: un caso dudoso se comunica como «caso poco claro; se recomienda valoración», sin bloquear la cita. El doctor ve una banda, el motivo en lenguaje claro y los dominios candidatos. La cola debe tener filtros, estados vacíos distintos, edad, reasignación y un 409 cuando otro revisor ya tomó el caso. Si no se define la pantalla y el endpoint, la validación queda escribible pero invisible.

### 12. Riesgo aceptado: la confianza no cambia la respuesta

**Decisión aceptada:** la confianza solo marca revisión posterior; no cambia la respuesta en el momento. La recomendación se entrega igual, con la especialidad y el botón que ya genera `_finalizar`. La validación del doctor y del super usuario sirve para control de calidad y aprendizaje, no para proteger al paciente de una orientación errónea en esa consulta.

La consecuencia debe quedar escrita: si el caso es dudoso, el paciente igual recibe una recomendación. La única forma de que la confianza cambie la respuesta sería degradar a una pregunta más o a `catalogo`/`derivar` antes de enviar; eso queda fuera de esta fase. El riesgo se acepta de forma explícita y se compensa con revisión posterior, muestreo y métricas de corrección.

### 13. Riesgos residuales

- Cobertura: una revisión opcional sin muestreo no genera datos suficientes para calibrar.
- Seguridad clínica: la confianza no cambia la respuesta; una orientación errónea se detecta después, no antes.
- Resumen: puede omitir un detalle que explique la decisión; por eso se guardan hashes y el vínculo a `mensajes` para reconstruir el caso.
- Sesgo: revisar solo casos de baja confianza deja fuera errores de alta confianza.
- Privacidad: la ficha y el motivo de corrección contienen datos clínicos.
- Dependencia de PHP: el catálogo y los pacientes siguen siendo externos.
- Complejidad: un modelo de dominio con `tipo`, cola de validación, propuestas y versiones para 4 dominios y 45 auditorías.
- Seguridad: la API key compartida no identifica a un doctor ni autoriza una aprobación.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Eliminar `knowledge/dominios.json` y `knowledge/aprendido.json` como fuente de verdad y mover el conocimiento a SQLite relacional.
  * Usar `dominio` como raíz con FKs reales y `PRAGMA foreign_keys=ON` en todas las conexiones.
  * Añadir identidad de `consulta` y `turno`, y enlazar mensajes, ficha, respuesta, auditoría y validación.
  * Guardar evidencia reproducible: ficha/respuesta, hashes, dominio, top-k, confianza y versiones.
  * Implementar un índice determinista de confianza y marcar casos dudosos o multi-dominio.
  * Permitir validación posterior y opcional del especialista sobre ficha y respuesta final.
  * Registrar correcciones y propuestas de palabras/preguntas con aprobación antes de publicar.
  * Migrar los datos actuales sin perder sesiones, mensajes ni auditorías.
  * Definir cola, roles, retención y métricas mínimas.

* **Out-of-Scope Non-Goals:**
  * Obligar al paciente a agendar o bloquear la recomendación.
  * Validación previa al envío en esta fase.
  * Cambiar la respuesta o degradar la especialidad según la confianza en esta fase.
  * Intervención en vivo de un doctor dentro del chat.
  * Validación de cada pregunta, del dominio o del razonamiento por parte del doctor.
  * Reemplazar `mensajes`, `sesiones`, `memorias` o `auditoria`.
  * Aprendizaje automático de la propia salida o publicación sin aprobación.
  * Diagnóstico, prescripción o tratamiento.
  * Normalizar `embedding`, `datos_json`, `estado_json` y `json_respuesta` en la misma fase; se hará en la fase 2 acordada.
  * Escalado multi-worker en esta fase.

## Alternatives Weighed

* **Mantener JSON como fuente y SQLite como caché:** rechazado por el autor. Quiere eliminar los archivos JSON como fuente de verdad.
* **Reemplazar `mensajes` y `auditoria` por tablas nuevas:** rechazado por el autor. Las tablas existentes se conservan; las nuevas son complementarias.
* **Validación obligatoria antes de responder:** rechazado por el autor. La recomendación no obliga al paciente y la corrección es posterior, para aprendizaje y calidad.
* **Cambiar la respuesta según la confianza:** rechazado por el autor. La confianza solo marca revisión posterior; no degrada ni retiene la recomendación en esta fase.
* **Aprendizaje automático a partir de la corrección:** rechazado. Una sola corrección puede ser sesgada; la publicación requiere aprobación. El LLM puede proponer, no publicar.
* **Enrutar la revisión por la especialidad sugerida:** rechazado por los revisores. Si la sugerencia es el error, el especialista correcto nunca ve el caso. Se propone revisor natural por especialidad con respaldo de administración; en esta fase solo el super usuario.
* **Un solo número de confianza:** rechazado por los revisores. No es explicable ni calibrable; se guardan componentes y versión.
* **Ocho tablas separadas por tipo:** rechazado por el autor. Prefiere una sola tabla `dominio_elemento` con FK a `dominio`; el profesor pidió la relación y así queda explícita.
* **Normalizar todas las columnas JSON en la primera migración:** rechazado para la primera fase por los revisores. Es una reescritura de estado, memoria y auditoría; se propone una fase posterior con contratos y pruebas propias.
* **Guardar la ficha completa en cada mensaje:** rechazado. Duplica PII y no todas las respuestas tienen ficha. Se propone guardar un resumen estructurado en el turno final, con hash y versión, y dejar el detalle en `mensajes`.
* **Reenviar toda la conversación a la cola o al LLM de revisión:** rechazado por el autor. Puede haber demasiados mensajes; se guarda un resumen y no se reenvía el historial completo.
* **Cola de validación sin endpoint ni pantalla:** rechazado. Sería una tabla invisible; se exige contrato de cola y UI en el sistema PHP existente.
* **Panel nuevo de validación en FastAPI:** rechazado por el autor. La validación vive en PHP; FastAPI solo expone los endpoints.

## Key Decisions & Staging for Next Steps

### Decisiones tomadas

1. La validación es posterior y opcional; el paciente no está obligado a agendar.
2. El doctor valida la ficha y la respuesta final; el dominio y el razonamiento siguen siendo de la IA.
3. El doctor de la especialidad puede validar, pero no está obligado.
4. No se reemplazan tablas; se añaden tablas complementarias.
5. La promoción al conocimiento requiere aprobación; la corrección puede registrarse sin aprobación.
6. Un índice determinista de confianza y la detección multi-dominio disparan la revisión.
7. El LLM puede proponer palabras y preguntas desde el motivo de corrección; no las publica.
8. La base de conocimiento pasa a SQLite relacional con FK a `dominio`.
9. Se acepta la separación por fases: fase 1 elimina los archivos JSON de conocimiento; fase 2 normaliza las columnas operativas.
10. El especialista es el revisor natural; si no valida, administración toma el caso. En esta fase solo el super usuario puede validar; el usuario que atiende queda para después.
11. La confianza solo marca revisión posterior; no cambia la respuesta que recibe el paciente.
12. La evidencia guarda un resumen estructurado de la ficha y la respuesta final, no la conversación completa.
13. La cola y la pantalla de validación viven en el sistema PHP existente; FastAPI expone los endpoints.
14. Las listas del dominio se guardan en una sola tabla `dominio_elemento` con FK a `dominio`; no se crean ocho tablas separadas.

### Decisiones abiertas

No quedan decisiones abiertas para este brief. La implementación puede empezar por la fase 1.

### Fases propuestas

| Fase | Entregable | Puerta de salida |
|---|---|---|
| 0 | Contrato de datos y decisiones abiertas | Alcance de evidencia, UI y modelo de conocimiento escritos. |
| 1 | Fundación de migración: `conectar()`, `schema_migrations`, backup, seed, FKs, deduplicación de alias | `foreign_key_check=0`; 10 sesiones, 90 mensajes, 45 auditorías preservados; 39 palabras reportadas como 29 + alias. |
| 2 | `consulta`, `turno`, evidencia, `mensaje_id` y transacción por turno | Cada orientación final tiene `consulta_id`, resumen de evidencia y enlace a mensaje/auditoría. |
| 3 | Detector de candidatos con puntajes, top-k, negación, orden determinista y componentes de confianza | Set dorado de frases ambiguas y negadas estable; versiones persistidas; la confianza solo marca revisión y no altera la respuesta. |
| 4 | API en FastAPI y cola en PHP: roles, asignación, estados, acceso auditado | Un doctor autorizado o el super usuario ve el resumen, filtra y decide; un rol falso no puede. |
| 5 | Propuestas de aprendizaje, aprobación, palabras/preguntas, capa de error y `kb_version` | Una propuesta no aprobada no cambia la detección; una aprobada sí, con prueba. |
| 6 | Normalización acordada de columnas operativas, salud y métricas | Contratos de `/sesiones`, `/auditoria` y `/conocimiento` preservados o versionados. |

### Criterios de éxito

- Cero FKs inertes: toda conexión tiene `foreign_keys=1` y `foreign_key_check` limpio.
- La migración conserva los datos actuales y falla de forma visible si la KB queda vacía.
- Toda orientación final tiene una consulta, un turno, evidencia, dominio nullable y confianza explicable.
- Una corrección no aprobada no modifica el conocimiento; una aprobada se aplica y se puede revertir.
- El flujo general y la emergencia tienen estado de revisión explícito, aunque sea «no aplica».
- La cola tiene dueño, edad, estados y métricas; no es una tabla pasiva.
- La respuesta al paciente no empeora por una revisión pendiente.

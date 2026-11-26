# Núcleo inteligente de MIDI (`ai`)

## Overview

`ai` concentra la lógica que decide qué preguntar, cómo detectar un dominio, cómo aprender frases y cómo redactar la orientación. No escribe en la base clínica. La única persistencia propia es `knowledge/aprendido.json`; el estado de la conversación lo manejan `main.py` y `storage/`.

La inteligencia es híbrida:

- **Simbólica:** `ai/cuestionario.py` usa palabras clave, señales de alarma y una máquina de estados.
- **Estadística:** `ai/embeddings.py` calcula similitud coseno para la memoria vectorizada.
- **Generativa:** `ai/gemini.py` y `ai/openai_compatible.py` redactan la orientación y ejecutan herramientas de solo lectura.

## Interface

### Proveedores

- `ai/base.py:ProveedorIA`: interfaz abstracta con `nombre_modelo`, `precargar_catalogo()` y `orientar(consulta, historial) -> dict`.
- `ai/proveedores.py:crear_proveedor()`: construye el proveedor principal según `PROVEEDOR_IA` y envuelve la cadena `PROVEEDORES_FALLBACK` en `ProveedorFallback`.
- `ai/proveedores.py:construir(nombre)`: acepta `gemini`, `opencode`, `groq`, `openai` y `custom`.
- `ai/proveedores.py:ProveedorFallback`: prueba proveedores en orden; guarda el último que respondió en `ultimo`; si todos fallan lanza `RuntimeError`.
- `ai/gemini.py:ProveedorGemini`: lee `guia.md` al construirse, inyecta el catálogo cacheado, usa `thinking_budget=0`, desactiva el *automatic function calling* y ejecuta hasta 4 iteraciones de herramientas.
- `ai/openai_compatible.py:ConfigProveedor`: configuración de cualquier endpoint compatible con OpenAI.
- `ai/openai_compatible.py:ProveedorOpenAICompatible`: usa `esquema_tool()` para convertir las funciones de `tools/clinica.py`; si el endpoint rechaza `response_format`, `temperature` o `tools`, los quita y reintenta; si no obtiene JSON válido, fuerza una llamada final sin herramientas.
- `ai/openai_compatible.py:mensajes_openai()`: convierte el historial de Gemini (`model`) al rol `assistant` de OpenAI.

### Cuestionario y aprendizaje

- `ai/cuestionario.py:dominios()`: fusiona `knowledge/dominios.json` con `knowledge/aprendido.json` y cachea el resultado en `_dominios_cache`.
- `ai/cuestionario.py:detectar_dominio(texto)`: coincidencia exacta de palabra clave o similitud Jaccard ≥ 0,6 con un ejemplo aprendido.
- `ai/cuestionario.py:aprender_ejemplo(dominio, frase)`: guarda una frase real; máximo 50 por dominio; deduplica por texto normalizado.
- `ai/cuestionario.py:aprender_palabras(dominio, palabras)`: agrega palabras clave manuales; deduplica.
- `ai/cuestionario.py:listar_aprendido()`: devuelve el contenido crudo de `aprendido.json`.
- `ai/cuestionario.py:nueva_sesion(dominio, motivo)`: crea la ficha del cuestionario.
- `ai/cuestionario.py:hay_alarma(texto, dominio)`: busca señales de alarma del dominio como subcadena normalizada.
- `ai/cuestionario.py:proxima_pregunta(estado)`: devuelve la primera pregunta no respondida; `None` al llegar a `max_preguntas`.
- `ai/cuestionario.py:registrar_respuesta(estado, texto)`: registra la respuesta de `estado["siguiente_pregunta"]` y la marca como hecha.
- `ai/cuestionario.py:es_suficiente(estado)`: verdadero al alcanzar `min_preguntas`.
- `ai/cuestionario.py:progreso(estado)`: porcentaje basado en `min_preguntas`.
- `ai/cuestionario.py:especialidad_candidata(estado, catalogo)`: primera especialidad configurada que exista en el catálogo; si ninguna existe, intenta `CONSULTA GENERAL`; si tampoco está, devuelve `None`.
- `ai/cuestionario.py:resumen_contexto(contexto)`: resume patologías y los últimos 5 controles.
- `ai/cuestionario.py:construir_ficha(estado, contexto, catalogo, recuerdos)`: texto que recibe el proveedor para la orientación final.

### Esquema y prompt

- `ai/schemas.py:RespuestaOrientacion`: tipos `emergencia`, `orientacion`, `catalogo`, `aclaracion`, `derivar`, `datos`, `navegacion` y `registro_paciente`; campos de especialidad, listas clínicas, progreso, borrador de paciente y `accion_sugerida`.
- `ai/schemas.py:AccionSugerida`: etiqueta, ruta y visibilidad del botón.
- `ai/comun.py:leer_guia()`: lee `guia.md`.
- `ai/comun.py:system_prompt(guia)`: guía + catálogo cacheado + instrucciones de tools, datos propios, registro de paciente y navegación.
- `ai/comun.py:construir_accion(r)`: construye el botón; no lo decide el modelo.
- `ai/comun.py:validar_respuesta(r)`: vacía la especialidad en tipos que no la admiten, descarta módulos inválidos y degrada a `catalogo` si la especialidad no existe.
- `ai/comun.py:limpiar_json(texto)`: quita bloques Markdown.
- `ai/embeddings.py:embed(texto)`: vector de `EMBEDDING_MODEL` o `None` si falla.
- `ai/embeddings.py:coseno(a, b)`: similitud coseno.

### Datos que consume

- `knowledge/dominios.json`: conocimiento curado (dominios, preguntas, palabras, alarmas, especialidades, pruebas, asociaciones y hallazgos).
- `knowledge/aprendido.json`: ejemplos y palabras aprendidas en runtime.
- `guia.md`: prompt del sistema.
- Catálogo de especialidades: se obtiene de `tools/php_client.py`, no de `ai`.

## Invariants

- **Detección determinista.** `detectar_dominio` recorre los dominios en el orden del JSON. La primera palabra clave que coincide gana. Si no hay coincidencia exacta, solo acepta un ejemplo aprendido con similitud ≥ 0,6.
- **Caché de dominios.** `dominios()` no relee los JSON en cada llamada. Solo `aprender_ejemplo` y `aprender_palabras` invalidan `_dominios_cache`; una edición manual de `dominios.json` requiere reiniciar el proceso o invalidar la caché.
- **Ficha de sesión.** `nueva_sesion` devuelve `dominio`, `motivo`, `paciente_id`, `paciente_cedula`, `paciente_nombre`, `preguntas_hechas`, `respuestas`, `siguiente_pregunta`, `contexto`, `contexto_cargado` y `completo`.
- **Una respuesta por turno.** `registrar_respuesta` no hace nada si `siguiente_pregunta` está vacío. `main.py` limpia `siguiente_pregunta` después de registrar.
- **Cierre por mínimo o máximo.** `es_suficiente` cierra al llegar a `min_preguntas`; `proxima_pregunta` devuelve `None` al llegar a `max_preguntas`. El flujo de `main.py` puede finalizar por cualquiera de las dos condiciones.
- **Alarma prevalece.** `hay_alarma` se evalúa sobre el motivo y todas las respuestas; una coincidencia produce `emergencia` y no se hacen más preguntas.
- **Especialidad candidata.** `especialidad_candidata` recorre `dominio["especialidades"]` en orden y devuelve la primera que exista en el catálogo. Si ninguna coincide, intenta `CONSULTA GENERAL`; si tampoco está, devuelve `None`. No hay una marca explícita de «último recurso»: la posición en la lista es la única prioridad.
- **Aprendizaje automático.** `main.py` llama a `aprender_ejemplo` cada vez que detecta un dominio nuevo. `ai/cuestionario.py` no decide por sí solo aprender; solo escribe cuando se le invoca.
- **Límite de ejemplos.** `aprender_ejemplo` conserva los últimos 50 ejemplos por dominio y deduplica por texto normalizado sin tildes ni mayúsculas.
- **Sin borrado de aprendizaje.** No existe función para eliminar un ejemplo o una palabra aprendida; `POST /conocimiento` solo agrega.
- **Validación de salida.** `validar_respuesta` vacía `especialidad_sugerida` en `emergencia`, `catalogo`, `datos`, `navegacion` y `registro_paciente`; si la especialidad no está en el catálogo, cambia el tipo a `catalogo` y devuelve las opciones reales.
- **Dos validaciones.** `ProveedorGemini._con_modelo` duplica las comprobaciones de especialidad y navegación en lugar de llamar a `ai/comun.py:validar_respuesta`; `ProveedorOpenAICompatible` sí usa la función compartida. Cualquier cambio de guardrails debe aplicarse en ambos sitios.
- **Prompt cacheado.** Ambos proveedores leen `guia.md` al construirse. Un cambio en la guía requiere reiniciar el servicio.
- **Acción en Python.** `accion_sugerida` se construye con `_construir_accion` o `comun.construir_accion`; el modelo no decide la ruta ni el botón.
- **Borrador de paciente.** `RespuestaOrientacion.paciente_borrador` permite devolver datos para que PHP confirme el alta; `ai` no escribe pacientes.

## Side Effects

- Peticiones HTTP GET al sistema PHP a través de `tools/php_client.py` (catálogo y herramientas).
- Peticiones HTTP a los proveedores de IA configurados.
- Escritura de `knowledge/aprendido.json` en `aprender_ejemplo` y `aprender_palabras`.
- Lectura de `guia.md`, `knowledge/dominios.json` y `knowledge/aprendido.json`.
- Logs de errores, herramientas y diagnósticos.
- Si `IA_DEBUG=true`, escritura de payloads crudos en `IA_DEBUG_DIR` (`storage/debug_ia` por defecto).
- Sin escritura directa en SQLite; `main.py` y `storage/` son los dueños de esa persistencia.
- Sin escritura en MySQL ni en la historia clínica.

## Verification

- Run: `pytest`
- Pruebas relacionadas: `tests/test_aprendizaje.py`, `tests/test_gemini_fallback.py`, `tests/test_proveedores.py`, `tests/test_tools.py`.
- Nota: las pruebas de integración requieren `.env`, claves de proveedor y PHP disponible. No ejecutar contra producción sin una copia controlada.

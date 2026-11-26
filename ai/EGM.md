# Núcleo inteligente de MIDI (`ai`)

## Overview

`ai` concentra la lógica que decide qué preguntar, cómo detectar un dominio, cómo evaluar evidencia y confianza, cómo aprender frases y cómo redactar la orientación. No escribe en la base clínica ni abre MariaDB.

La inteligencia es híbrida:

- **Simbólica:** `cuestionario.py` usa la KB activa, palabras clave, señales de alarma y una máquina de estados.
- **Estadística:** `embeddings.py` calcula similitud coseno para la memoria vectorizada.
- **Calibrada:** `confianza.py` pondera seis componentes para decidir si un caso va a revisión.

La KB curada vive en SQLite. `knowledge/dominios.json` y `knowledge/aprendido.json` son solo semilla de migración y respaldo de arranque.

## Interface

### `ai/cuestionario.py`

- `dominios()`: snapshot de la KB activa desde `storage.conocimiento.snapshot_sincrono()`.
- `detectar_candidatos(texto, limite=3)`: ranking de dominios por keyword positiva o similitud de ejemplo.
- `detectar_dominio(texto)`: primer candidato con `score >= 0.60`.
- `hay_alarma(texto, dominio)`: delega en `evidencia.hay_alarma` con las señales del dominio.
- `nueva_sesion(dominio, motivo)`, `proxima_pregunta(estado)`, `registrar_respuesta(estado, texto)`, `es_suficiente(estado)`, `progreso(estado)`.
- `especialidad_candidata(estado, catalogo)`: primera especialidad del dominio presente en el catálogo; fallback a `CONSULTA GENERAL`.
- `construir_ficha(estado, contexto, catalogo, recuerdos=None)`: prompt clínico de cierre.
- `aprender_ejemplo(dominio, frase)` y `aprender_palabras(dominio, palabras)`: escriben en SQLite vía `storage.conocimiento`; no se llaman automáticamente desde `/orientar`.
- `listar_aprendido()`: elementos con `origen = 'aprendido'`.

### `ai/evidencia.py`

- `normalizar(texto)`: NFD, minúsculas, sin acentos.
- `tokenizar(texto)`, `tokens(texto)`, `similitud(a, b)`.
- `detectar_evidencia(texto, terminos, ventana=8)`: coincidencias con polaridad y offsets; la negación se corta en `pero/aunque/sino/embargo` y en `, ; .`.
- `coincide(texto, terminos)`, `hay_alarma(texto, terminos)`, `contar_negaciones(texto)`.

### `ai/confianza.py`

- `PESOS`: `coincidencia_keyword` 0.35, `similitud_ejemplo` 0.20, `margen_top1_top2` 0.20, `num_candidatos` 0.10, `preguntas_respondidas` 0.10, `penalizacion_negacion` 0.05.
- `componentes(...)`, `calcular(componentes)`, `margen(top1, top2)`, `banda(confianza)`.
- `evaluar(...)`: devuelve `(revisar, motivo)`; `aclaracion` nunca revisa.
- `es_muestra(turno_id)`: 5 % determinista por SHA-256.

### `ai/embeddings.py`

- `embed(texto)`: embedding Gemini opcional; devuelve `None` si no hay cliente o falla.
- `coseno(a, b)`: similitud coseno.

### Proveedores

- `base.ProveedorIA`: interfaz abstracta.
- `gemini.ProveedorGemini`, `openai_compatible.ProveedorOpenAICompatible`.
- `proveedores.ProveedorFallback`, `construir(nombre)`, `crear_proveedor()`.
- `ai/__init__.py` reexporta proveedores y `ConfigProveedor`.

### `ai/comun.py`

- `leer_guia()`, `system_prompt(guia)`, `construir_accion(r)`, `validar_respuesta(r)`, `limpiar_json(texto)`.

### `ai/schemas.py`

- `AccionSugerida`: etiqueta, ruta y visibilidad.
- `RespuestaOrientacion`: tipo, mensaje, especialidad, listas clínicas, módulo, acción y campos de paciente.

## Invariants

- **KB desde SQLite.** `cuestionario.dominios()` no lee JSON en runtime; si la base no tiene KB, usa el JSON solo como respaldo de arranque.
- **Detección determinista.** La negación es por cláusula; dos marcadores (doble negación) no niegan. El umbral de ejemplo es `0.60`.
- **Candidatos estables.** `detectar_candidatos` ordena por score y conserva el orden de la KB en empates.
- **Sin aprendizaje implícito.** `main._procesar` ya no llama a `aprender_ejemplo`; las frases nuevas entran como propuestas. Las funciones `aprender_*` quedan para uso explícito/compatibilidad y escriben SQLite.
- **Confianza no gating.** La confianza no cambia `tipo_respuesta` ni la especialidad; solo decide revisión.
- **Pesos fijos.** Los seis pesos suman 1.0; `calcular` acota el resultado a 0..1.
- **Muestra determinista.** `es_muestra` depende solo de `turno_id`, no de aleatoriedad del proceso.
- **Proveedor con respaldo.** `crear_proveedor` construye el principal y, si está configurado, la cadena de fallback; un fallback mal configurado se omite con log.
- **Sin MariaDB.** `ai` no importa ni abre MySQL; la única persistencia es SQLite a través de `storage`.
- **Embeddings opcionales.** Si Gemini no responde, la memoria sigue funcionando sin vector.

## Side Effects

- Llamadas HTTP a proveedores de IA y a Gemini para embeddings.
- Lectura/escritura de SQLite vía `storage.conocimiento` cuando se usan funciones de aprendizaje.
- Caché de la KB en `storage.conocimiento` y cliente de embeddings en `ai.embeddings`.
- Logs de errores de proveedor y de embeddings.
- Sin escritura en MySQL, sin archivos clínicos y sin correo.

## Verification

- Run: `python -m pytest -q`
- Pruebas específicas: `tests/test_evidencia_engine.py`, `tests/test_alarma.py`, `tests/test_confianza.py`, `tests/test_aprendizaje.py`, `tests/test_proveedores.py`.
- Nota: las pruebas de proveedores usan dobles; no requieren una clave real de Gemini.

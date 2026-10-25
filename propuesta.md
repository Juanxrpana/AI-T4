# Propuesta — Cuestionario de orientación médica + Sistema experto

> Documento de diseño. Estado: propuesta para revisión (no implementada).

## 1. Pendientes de confirmar

1. Columnas reales de `control` y `patologías` (afinar contrato PHP).
2. Si la secretaria ya tiene pantalla de búsqueda de pacientes (reutilizar vs.
   crear `apiBuscarPaciente`).
3. Los 3 dominios exactos y sus preguntas/pruebas (validar con el profesor).

## 2. Objetivo

Evolucionar el asistente actual (orientación por un solo síntoma → derivación
inmediata) hacia un **cuestionario guiado** que:

- Lea los **síntomas previos** del paciente (tablas `control` y `patologías`).
- **No derive con un solo síntoma**: recabe información progresiva antes de
  referir a un especialista.
- Ofrezca una orientación **más detallada y predictiva, tipo médico**,
  sugiriendo **pruebas/exámenes orientativos**.
- **Sin dar diagnóstico** (restricción del profesor): solo orientar y derivar.
- Mantenga **auditoría** (punto A) y **memoria persistente** (punto D).

## 3. Estado actual (componente AI-T4)

| Pieza | Situación | Limitación |
|---|---|---|
| Base de conocimiento | `guia_compacta.md` + catálogo inyectado (`ai/gemini.py`) | Lenguaje natural, no reglas formales |
| Memoria | `SESIONES` en RAM (`main.py`) | Se pierde al reiniciar |
| Motor de inferencia | Gemini (LLM) | No determinista, no trazable |
| Datos de paciente | `mis_datos()` lee solo al **usuario logueado** | No lee a un paciente tercero |
| Auditoría | `logger.info` (efímero) + bitácora PHP | Sin registro estructurado/consultable |

**Conclusión:** el componente actual es un híbrido LLM + base de conocimiento,
pero **no** es un sistema experto clásico (le falta motor de inferencia
determinista, memoria de hechos y trazabilidad).

## 4. Gap crítico de datos

`mis_datos()` (`tools/clinica.py`) resuelve el paciente del **usuario logueado**
por cédula. El nuevo flujo necesita leer `control` y `patologías` de un
**paciente arbitrario** (el que llama a pedir cita). Requiere:

1. Mecanismo para buscar/seleccionar paciente (cédula/nombre).
2. Endpoints PHP nuevos que hoy no existen.

## 5. Decisiones confirmadas

1. **Paciente**: búsqueda por cédula/nombre (nuevo endpoint PHP).
2. **Motor del cuestionario**: híbrido — reglas Python (state machine) + Gemini
   (redacción/explicación).
3. **Base de conocimiento**: JSON estructurado en el componente, inyectado por
   dominio.
4. **Alcance MVP**: 3 dominios (dolor torácico, fiebre, dolor abdominal).

## 6. Arquitectura y flujo

```
secretaria escribe síntoma
   → [detección de dominio] Gemini clasifica a 1 de los 3 dominios (o "sin dominio")
   → [selección de paciente] buscar por cédula/nombre  → GET /Api/apiBuscarPaciente
   → [contexto clínico] control + patologías del paciente
        → GET /Api/apiControlesPaciente + apiPatologiasPaciente
   → [CUESTIONARIO] motor Python elige la siguiente pregunta del dominio
        (salta preguntas ya respondidas por el historial)
   → [¿info suficiente?] NO → repite pregunta | SÍ → Gemini redacta orientación
   → [orientación final] especialidad candidata + pruebas_sugeridas (orientativas)
   → [auditoría] todo el intercambio append-only en SQLite
```

## 7. Modelo de datos (SQLite local, `storage/db.py`)

SQLite local al componente (no toca MariaDB → respeta "FastAPI no toca la BD
clínica"). Nuevo módulo `storage/` con `aiosqlite`.

```
sesiones(session_id PK, creada_en, estado_json)   -- ficha cuestionario + historial
mensajes(session_id FK, ts, rol, texto)
auditoria(id AUTOINC, ts, session_id, usuario_id, usuario_rol, usuario_nombre,
          paciente_id, dominio, consulta, tipo_respuesta, especialidad_sugerida,
          pruebas_sugeridas, modelo_usado, latencia_ms, tools_usadas, json_respuesta)
```

`estado_json` (ficha del cuestionario):

```json
{
  "dominio": "dolor_toracico",
  "paciente_id": 123,
  "preguntas_hechas": ["intensidad", "irradiacion"],
  "respuestas": {"intensidad": "moderada", "irradiacion": "brazo izquierdo"},
  "siguiente_pregunta": "sudoracion",
  "especialidad_candidata": "Cardiología",
  "completo": false
}
```

## 8. Contrato de datos nuevo (PHP, `ControllerApi.php` + `ModeloApi.php`)

Todos requieren `X-API-Key`. *(Columnas exactas de `control`/`patologías` por
confirmar — ver sección 1.)*

| Endpoint | Devuelve | Nota |
|---|---|---|
| `GET /Api/apiBuscarPaciente?q=...` | `[{id_paciente, nombre, cedula}]` | límite 10 |
| `GET /Api/apiControlesPaciente/{id}` | `[{fecha, motivo, hallazgos, diagnostico_previo}]` | filas de `control` |
| `GET /Api/apiPatologiasPaciente/{id}` | `[{nombre, fecha_diagnostico}]` | patologías del paciente |
| `GET /Api/apiCatalogoPatologias` | `[{nombre, sintomas[], especialidad}]` | base de conocimiento (cache 10 min) |

En `tools/php_client.py`: nuevos métodos + caché. Nueva tool
`datos_clinicos_paciente()` (por contexto, como `mis_datos`).

## 9. Base de conocimiento (`knowledge/dominios.json`)

```json
{
  "dolor_toracico": {
    "especialidades": ["Cardiología", "Medicina Interna"],
    "senal_alarma": ["dolor opresivo", "irradia a brazo", "sudoración", "disnea"],
    "preguntas": [
      {"id": "intensidad", "texto": "¿Qué tan intenso es el dolor, del 1 al 10?"},
      {"id": "irradiacion", "texto": "¿Se irradia a brazo, mandíbula o espalda?"},
      {"id": "esfuerzo", "texto": "¿Aparece con esfuerzo o en reposo?"}
    ],
    "min_preguntas": 3,
    "pruebas": ["Electrocardiograma", "Troponinas", "Radiografía de tórax"]
  }
}
```

Es lo que hace "predictivo tipo doctor" **sin diagnosticar**: asocia hallazgos a
especialidades y pruebas orientativas, siempre como "podría indicarse".

## 10. Motor híbrido (`ai/cuestionario.py`)

- `detectar_dominio(consulta)` → Gemini clasifica a 1 dominio (o `None`).
- `proxima_pregunta(estado, contexto_clinico)` → regla Python; salta las ya
  respondidas por `control`/`patologías`.
- `es_suficiente(estado)` → `preguntas_hechas >= min_preguntas` o hay señal de
  alarma (→ derivación/emergencia inmediata).
- `construir_ficha(estado, contexto)` → texto inyectado a Gemini para redactar.

Gemini **no** decide cuándo parar ni qué preguntar: solo clasifica dominio,
interpreta la respuesta libre del usuario y redacta.

## 11. Guía y esquema de respuesta

- **`guia_compacta.md`**: nueva sección "Protocolo de entrevista" — no derivar
  con 1 síntoma; usar la ficha; lenguaje de descarte.
- **`ai/schemas.py`** (`RespuestaOrientacion`): añadir
  - `pruebas_sugeridas: list[str]`
  - `pregunta_activa: str` (reutiliza `aclaracion`, ahora con `progreso`)
  - `progreso: int` (0–100)
  - `informacion_recopilada: dict`
- **`ai/gemini.py:104`** (`_construir_accion`): sin botón hasta `completo`.

## 12. Límite "no diagnóstico"

- **Permitido**: "puede estar relacionado con…", "habría que descartar…",
  "suelen indicarse pruebas como…".
- **Prohibido**: "tiene", "es", "compatible con", "le indico X".
- `pruebas_sugeridas` siempre con el cierre "a confirmar por el médico".

## 13. Archivos a tocar y fases

| Fase | Archivos | Contenido |
|---|---|---|
| F1 — Fundación | `storage/db.py`, `storage/sesiones.py`, `storage/auditoria.py`, `requirements.txt` | SQLite + repositorios |
| F2 — Memoria/auditoría | `main.py` | reemplazar `SESIONES`, escribir auditoría, `GET /auditoria` |
| F3 — Datos clínicos | `tools/php_client.py`, `tools/clinica.py` | endpoints nuevos + tool `datos_clinicos_paciente` |
| F4 — Conocimiento | `knowledge/dominios.json` | 3 dominios |
| F5 — Motor | `ai/cuestionario.py`, `ai/gemini.py`, `ai/base.py` | state machine + integración |
| F6 — Guía + esquema | `guia_compacta.md`, `guia.md`, `ai/schemas.py` | protocolo + campos |
| F7 — Tests | `tests/*` | cuestionario, "no derivar con 1 síntoma", auditoría, persistencia |

**Repo PHP** (contrato): `ControllerApi.php` (4 endpoints), `ModeloApi.php`
(consultas `control`/`patologías`), `modalChat.php` + `chatModal.js` (progreso,
respuestas rápidas, pruebas sugeridas).

## 14. Riesgos

- **Costo de tokens**: guía rica + patologías + historial. Mitigación: inyectar
  solo el dominio relevante y resumir `control` (top N).
- **Límite diagnóstico vs predictivo**: "sugerir exámenes" es delicado; debe
  quedar como orientación y condicionada al médico.
- **Privacidad**: la auditoría guarda datos sensibles → retención/borrado y
  control de acceso al `GET /auditoria`.

# Configuración y rutas del asistente

## Overview

`config` concentra las variables de entorno de FastAPI, la URL base del sistema PHP, la clave compartida, los proveedores de IA, la persistencia SQLite y las rutas del frontend que el asistente ofrece como botones.

## Interface

### `config/settings.py`

`Settings` (Pydantic Settings) lee `.env` y expone:

- `GEMINI_API_KEY`: obligatorio, aunque el proveedor activo no sea Gemini.
- `PHP_BASE_URL`: base del sistema PHP. Valor por defecto: `http://localhost/Sistema-del--CEM--JEHOVA-RAFA`.
- `API_KEY_COMPARTIDA`: obligatorio; debe coincidir con `API_KEY_IA` de CEMJR.
- `MODELO_GEMINI`: obligatorio.
- `MODELOS_FALLBACK`: modelos Gemini de respaldo, separados por comas.
- `IA_TIMEOUT_MODELO`: segundos por modelo; valor por defecto `12.0`.
- `CORS_ORIGINS`: lista separada por comas; vacío significa sin CORS.
- `SQLITE_PATH`: base local del componente (`storage/midi.db` por defecto).
- `HISTORIAL_MESES`: ventana de controles clínicos; valor por defecto `6`.
- `APRENDIZAJE_PATH`: archivo de aprendizaje (`knowledge/aprendido.json` por defecto).
- `EMBEDDING_MODEL`: modelo de embeddings (`gemini-embedding-001` por defecto).
- `PROVEEDOR_IA`: proveedor principal; valor por defecto `opencode`.
- `PROVEEDORES_FALLBACK`: cadena de respaldo separada por comas; vacía por defecto.
- `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `MODELO_OPENCODE`, `MODELOS_FALLBACK_OPENCODE`.
- `GROQ_API_KEY`, `GROQ_BASE_URL`, `MODELO_GROQ`, `MODELOS_FALLBACK_GROQ`.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `MODELO_OPENAI`, `MODELOS_FALLBACK_OPENAI`.
- `CUSTOM_API_KEY`, `CUSTOM_BASE_URL`, `MODELO_CUSTOM`, `MODELOS_FALLBACK_CUSTOM`.
- `IA_DEBUG` (falso por defecto) e `IA_DEBUG_DIR` (`storage/debug_ia` por defecto).

### `config/modulos.py`

- `BASE`: prefijo de las rutas; hoy es `/`.
- `RUTAS_FRONTEND`: rutas web para botones (`citas_nueva` y `citas_hoy` apuntan a `/Citas/citasHoy`; también `Citas/citas`, `Citas/citasRealizadas`, `Pacientes/getPacientes`, `Clientes/Clientes`, `Doctores/doctores`, `Servicios/servicios`, `Hospitalizacion/hospitalizacion`, `Insumos/insumos`, `Insumos/InsumosVencidos`, `Reportes/reportes`).
- `ETIQUETAS_MODULOS`: etiqueta visible de cada módulo.
- `ruta_cita_con_especialidad(nombre)`: arma `/Citas/citasHoy?especialidad=...` con `urllib.parse.quote`.

### `config/__init__.py`

Reexporta `settings`, `RUTAS_FRONTEND`, `ETIQUETAS_MODULOS` y `ruta_cita_con_especialidad`.

## Invariants

- **`.env` obligatorio.** `Settings` exige `GEMINI_API_KEY`, `API_KEY_COMPARTIDA` y `MODELO_GEMINI`; sin ellos el servicio no arranca, incluso si el proveedor activo es OpenCode, Groq, OpenAI o custom.
- **Proveedor principal explícito.** `PROVEEDOR_IA` vale `opencode` por defecto. `crear_proveedor()` falla si el proveedor elegido no tiene clave, base URL o modelo; un respaldo mal configurado solo se registra como advertencia y se omite.
- **La URL de PHP debe apuntar a la raíz real.** El valor por defecto usa el nombre antiguo del proyecto; el `.env` actual debe apuntar a la raíz donde se sirve CEMJR. Si se sirve en un subdirectorio o por HTTP, los endpoints `/Api/...` fallan.
- **La clave compartida debe coincidir.** `API_KEY_COMPARTIDA` de AI-T4 y `API_KEY_IA` de CEMJR deben ser iguales.
- **Las rutas de `modulos.py` son del frontend, no endpoints de datos.** No consultan disponibilidad ni crean citas; solo generan enlaces para el navegador.
- **CORS vacío por defecto.** El navegador no llama a FastAPI directamente; el proxy es PHP.
- **SQLite es local.** `storage/midi.db` guarda sesiones, memoria y auditoría; no es la base clínica.
- **Configuración al importar.** `config/settings.py` construye `settings` al importarse; un cambio en `.env` requiere reiniciar el proceso.

## Side Effects

- Lectura de `.env`.
- Uso de `PHP_BASE_URL` en todas las llamadas del cliente.
- Rutas que el frontend abrirá en el navegador.
- Sin escritura en MySQL.

## Verification

- Run: `pytest`
- Nota: las pruebas que usan `Settings` requieren `.env`; verificar que `PHP_BASE_URL` y `API_KEY_COMPARTIDA` apunten al entorno correcto.

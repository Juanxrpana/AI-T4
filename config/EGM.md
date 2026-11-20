# Configuración y rutas del asistente

## Overview

`config` concentra las variables de entorno de FastAPI, la URL base del sistema PHP, la clave compartida, los proveedores de IA, la persistencia SQLite y las rutas del frontend que el asistente ofrece como botones.

## Interface

### `config/settings.py`

`Settings` (Pydantic Settings) lee `.env` y expone:

- `PHP_BASE_URL`: base del sistema PHP. Valor por defecto: `http://localhost/Sistema-del--CEM--JEHOVA-RAFA`.
- `API_KEY_COMPARTIDA`: clave que debe coincidir con `API_KEY_IA` de CEMJR.
- `CORS_ORIGINS`: lista separada por comas; vacío significa sin CORS.
- `SQLITE_PATH`: base local del componente (`storage/midi.db` por defecto).
- `HISTORIAL_MESES`: ventana de controles clínicos.
- `APRENDIZAJE_PATH` y `knowledge/dominios.json`: reglas y ejemplos del cuestionario.
- `EMBEDDING_MODEL`, `GEMINI_API_KEY`, `MODELO_GEMINI`, `MODELOS_FALLBACK`.
- `PROVEEDOR_IA`, `PROVEEDORES_FALLBACK`, claves y modelos de OpenCode, Groq, OpenAI y proveedor custom.
- `IA_TIMEOUT_MODELO`, `IA_DEBUG`, `IA_DEBUG_DIR`.

### `config/modulos.py`

- `RUTAS_FRONTEND`: rutas web para botones (`Citas/citasHoy`, `Citas/citas`, `Pacientes/getPacientes`, `Clientes/Clientes`, `Doctores/doctores`, `Servicios/servicios`, `Hospitalizacion/hospitalizacion`, `Insumos/insumos`, `Insumos/InsumosVencidos`, `Reportes/reportes`).
- `ETIQUETAS_MODULOS`: etiqueta visible de cada módulo.
- `ruta_cita_con_especialidad(nombre)`: arma `/Citas/citasHoy?especialidad=...`.

### `config/__init__.py`

Reexporta `settings`, `RUTAS_FRONTEND`, `ETIQUETAS_MODULOS` y `ruta_cita_con_especialidad`.

## Invariants

- **`.env` obligatorio.** `Settings` exige `GEMINI_API_KEY`, `API_KEY_COMPARTIDA` y `MODELO_GEMINI`; sin ellos el servicio no arranca.
- **La URL de PHP debe apuntar a la raíz real.** El valor por defecto usa el nombre antiguo del proyecto; el `.env` actual usa `https://127.0.0.1`. Si CEMJR se sirve en `/repo/CEMJR` o por HTTP, los endpoints `/Api/...` fallan.
- **La clave compartida debe coincidir.** `API_KEY_COMPARTIDA` de AI-T4 y `API_KEY_IA` de CEMJR deben ser iguales. En la revisión actual coinciden.
- **Las rutas de `modulos.py` son del frontend, no endpoints de datos.** No consultan disponibilidad ni crean citas; solo generan enlaces para el navegador.
- **CORS vacío por defecto.** El navegador no llama a FastAPI directamente; el proxy es PHP.
- **SQLite es local.** `storage/midi.db` guarda sesiones, memoria y auditoría; no es la base clínica.

## Side Effects

- Lectura de `.env`.
- Uso de `PHP_BASE_URL` en todas las llamadas del cliente.
- Rutas que el frontend abrirá en el navegador.
- Sin escritura en MySQL.

## Verification

- Run: `pytest`
- Nota: las pruebas que usan `Settings` requieren `.env`; verificar que `PHP_BASE_URL` y `API_KEY_COMPARTIDA` apunten al entorno correcto.

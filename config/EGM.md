# Configuración y rutas del asistente (`config`)

## Overview

`config` concentra las variables de entorno de FastAPI, la URL base del sistema PHP, la clave compartida, los proveedores de IA, la persistencia SQLite y las rutas del frontend que el asistente ofrece como botones.

No abre bases de datos ni escribe archivos; solo construye la configuración al importarse.

## Interface

### `config/settings.py`

`Settings` (Pydantic Settings) lee `.env` y expone:

- `GEMINI_API_KEY`: obligatorio, aunque el proveedor activo no sea Gemini.
- `PHP_BASE_URL`: base del sistema PHP. Valor por defecto heredado: `http://localhost/Sistema-del--CEM--JEHOVA-RAFA`.
- `API_KEY_COMPARTIDA`: obligatorio; debe coincidir con `API_KEY_IA` de CEMJR.
- `MODELO_GEMINI`: obligatorio.
- `MODELOS_FALLBACK`: modelos Gemini de respaldo, separados por comas.
- `IA_TIMEOUT_MODELO`: segundos por modelo; por defecto `12.0`.
- `CORS_ORIGINS`: lista separada por comas; vacío significa sin CORS.
- `SQLITE_PATH`: base local del componente (`storage/midi.db` por defecto). Contiene la KB, sesiones, identidad, evidencia y auditoría.
- `HISTORIAL_MESES`: ventana de controles clínicos; por defecto `6`.
- `APRENDIZAJE_PATH`: JSON de aprendizaje (`knowledge/aprendido.json` por defecto). Hoy es semilla/respaldo; el runtime lee SQLite.
- `EMBEDDING_MODEL`: modelo de embeddings (`gemini-embedding-001` por defecto).
- `PROVEEDOR_IA`: proveedor principal; por defecto `opencode`.
- `PROVEEDORES_FALLBACK`: cadena de respaldo separada por comas.
- `OPENCODE_*`, `GROQ_*`, `OPENAI_*`, `CUSTOM_*`: claves, URLs, modelos y fallbacks por proveedor.
- `IA_DEBUG` (falso por defecto) e `IA_DEBUG_DIR` (`storage/debug_ia` por defecto).

### `config/modulos.py`

- `BASE`: prefijo de las rutas; hoy `/`.
- `RUTAS_FRONTEND`: rutas web para botones (`Citas/citasHoy`, `Citas/citas`, `Citas/citasRealizadas`, `Pacientes/getPacientes`, `Clientes/Clientes`, `Doctores/doctores`, `Servicios/servicios`, `Hospitalizacion/hospitalizacion`, `Insumos/insumos`, `Insumos/InsumosVencidos`, `Reportes/reportes`).
- `ETIQUETAS_MODULOS`: etiqueta visible de cada módulo.
- `ruta_cita_con_especialidad(nombre)`: arma `/Citas/citasHoy?especialidad=...` con `urllib.parse.quote`.

### `config/__init__.py`

Reexporta `settings`, `RUTAS_FRONTEND`, `ETIQUETAS_MODULOS` y `ruta_cita_con_especialidad`.

## Invariants

- **`.env` obligatorio.** `Settings` exige `GEMINI_API_KEY`, `API_KEY_COMPARTIDA` y `MODELO_GEMINI`; sin ellos el servicio no arranca, incluso si el proveedor activo es otro.
- **Proveedor explícito.** `PROVEEDOR_IA` vale `opencode` por defecto; `crear_proveedor()` falla si el elegido no tiene clave, URL o modelo. Un fallback mal configurado se registra y se omite.
- **URL de PHP real.** El valor por defecto es heredado; el `.env` del host debe apuntar a la raíz donde se sirve CEMJR. Si está en un subdirectorio o por HTTP, `/Api/...` falla.
- **Clave compartida.** `API_KEY_COMPARTIDA` de AI-T4 y `API_KEY_IA` de CEMJR deben coincidir.
- **Rutas de frontend, no endpoints.** `modulos.py` solo genera enlaces; no consulta disponibilidad ni crea citas.
- **CORS vacío por defecto.** El navegador no llama a FastAPI directamente; el proxy es PHP.
- **SQLite local.** `storage/midi.db` no es la base clínica.
- **Configuración al importar.** Cambiar `.env` requiere reiniciar el proceso.

## Side Effects

- Lectura de `.env` al importar.
- Uso de `PHP_BASE_URL` y claves en las llamadas del cliente y proveedores.
- Rutas que el frontend abrirá en el navegador.
- Sin escritura en MySQL ni en archivos.

## Verification

- Run: `python -m pytest -q`
- Nota: las pruebas que usan `Settings` requieren `.env`; verificar que `PHP_BASE_URL` y `API_KEY_COMPARTIDA` apunten al entorno correcto.

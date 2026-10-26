"""Configuración común de los tests.

Se fijan variables de entorno ANTES de importar `main`/`config`, porque los
Settings de pydantic se construyen al importar. Las variables de entorno tienen
prioridad sobre el archivo `.env`, así que los tests no dependen de valores
reales.
"""

import os
import tempfile

os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["API_KEY_COMPARTIDA"] = "test-api-key"
os.environ["MODELO_GEMINI"] = "gemini-test"
os.environ["PHP_BASE_URL"] = "http://localhost/Sistema-del--CEM--JEHOVA-RAFA"
os.environ["CORS_ORIGINS"] = ""

_ruta_db = os.path.join(tempfile.gettempdir(), "midi_test.db")
if os.path.exists(_ruta_db):
    os.remove(_ruta_db)
os.environ["SQLITE_PATH"] = _ruta_db

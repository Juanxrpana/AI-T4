from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str
    PHP_BASE_URL: str = "http://localhost/Sistema-del--CEM--JEHOVA-RAFA"
    API_KEY_COMPARTIDA: str
    MODELO_GEMINI: str
    # Si el modelo principal falla (503/429) o tarda, se prueban estos en orden.
    MODELOS_FALLBACK: str = "gemini-3.5-flash,gemini-3.8-flash,gemini-3.1-flash-lite,gemini-3.7-flash"
    # Tiempo máximo por modelo (segundos) antes de pasar al siguiente.
    # La API de Gemini exige un mínimo de 10 s.
    IA_TIMEOUT_MODELO: float = 12.0
    # Lista separada por comas. Vacío = sin CORS (el navegador no llama directo).
    CORS_ORIGINS: str = ""
    # Persistencia local del componente (no toca MariaDB).
    SQLITE_PATH: str = "storage/midi.db"
    # Ventana de controles del paciente que se envía a MIDI.
    HISTORIAL_MESES: int = 6
    # Archivo donde se guardan los ejemplos/palabras que MIDI aprende.
    APRENDIZAJE_PATH: str = "knowledge/aprendido.json"
    # Modelo de embeddings para la memoria vectorizada.
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    # === Proveedores de IA ===
    # Proveedor principal y cadena de respaldo separada por comas.
    # Sin valor no se usa ningún proveedor implícito (Gemini incluido).
    # Ej.: PROVEEDOR_IA=opencode PROVEEDORES_FALLBACK=gemini
    PROVEEDOR_IA: str = "opencode"
    PROVEEDORES_FALLBACK: str = ""

    # OpenCode Go (OpenAI-compatible).
    OPENCODE_API_KEY: str = ""
    OPENCODE_BASE_URL: str = "https://opencode.ai/zen/go/v1"
    MODELO_OPENCODE: str = "deepseek-v4.1-flash"
    MODELOS_FALLBACK_OPENCODE: str = ""

    # Groq (OpenAI-compatible).
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    MODELO_GROQ: str = ""
    MODELOS_FALLBACK_GROQ: str = ""

    # OpenAI / ChatGPT (OpenAI-compatible).
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MODELO_OPENAI: str = ""
    MODELOS_FALLBACK_OPENAI: str = ""

    # Cualquier otro endpoint OpenAI-compatible (Ollama, vLLM, LM Studio...).
    CUSTOM_API_KEY: str = ""
    CUSTOM_BASE_URL: str = ""
    MODELO_CUSTOM: str = ""
    MODELOS_FALLBACK_CUSTOM: str = ""

    # Diagnóstico: guarda el payload crudo cuando una respuesta viene vacía.
    # Desactivado por defecto para no persistir datos clínicos.
    IA_DEBUG: bool = False
    IA_DEBUG_DIR: str = "storage/debug_ia"


settings = Settings()
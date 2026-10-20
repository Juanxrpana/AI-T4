from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str
    PHP_BASE_URL: str = "http://localhost/Sistema-del--CEM--JEHOVA-RAFA"
    API_KEY_COMPARTIDA: str
    MODELO_GEMINI: str
    # Si el modelo principal falla (503/429) o tarda, se prueban estos en orden.
    MODELOS_FALLBACK: str = "gemini-3.5-flash,gemini-2.5-flash,gemini-flash-latest"
    # Tiempo máximo por modelo (segundos) antes de pasar al siguiente.
    IA_TIMEOUT_MODELO: float = 12.0
    # Lista separada por comas. Vacío = sin CORS (el navegador no llama directo).
    CORS_ORIGINS: str = ""


settings = Settings()
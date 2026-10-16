from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str
    PHP_BASE_URL: str = "http://localhost/Sistema-del--CEM--JEHOVA-RAFA"
    API_KEY_COMPARTIDA: str
    MODELO_GEMINI: str


settings = Settings()
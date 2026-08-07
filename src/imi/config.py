from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = "Asia/Jakarta"
    database_url: str = "postgresql+psycopg://imi:change_me@localhost:5432/imi"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

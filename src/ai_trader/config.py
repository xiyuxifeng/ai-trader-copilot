from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AI_TRADER_",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://localhost/ai_trader_copilot"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://127.0.0.1:5173"
    worker_heartbeat_seconds: int = Field(default=30, ge=5, le=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()


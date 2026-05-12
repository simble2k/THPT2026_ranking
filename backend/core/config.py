from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/thpt2026"
    REDIS_URL: str = "redis://localhost:6379"
    DEBUG: bool = True
    ALLOWED_HOSTS: str = "*"

    # Scraper Settings
    SCRAPE_CONCURRENCY: int = 10
    SCRAPE_RETRY_LIMIT: int = 3

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_asyncpg_protocol(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

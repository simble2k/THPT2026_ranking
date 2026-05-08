from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/thpt2026"
    REDIS_URL: str = "redis://localhost:6379"
    DEBUG: bool = True
    ALLOWED_HOSTS: str = "*"

    # Scraper Settings
    SCRAPE_CONCURRENCY: int = 10
    SCRAPE_RETRY_LIMIT: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

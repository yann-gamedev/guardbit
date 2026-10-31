from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./guardbit.db"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    SCAN_MAX_PAGES: int = Field(default=30, ge=1)
    SCAN_DELAY_SECONDS: float = Field(default=2, ge=2)
    SNAPSHOT_DIR: Path = Path("./snapshots")
    LLM_API_KEY: SecretStr = SecretStr("")
    DEBUG: bool = False


settings = Settings()

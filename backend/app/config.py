from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
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

    @field_validator("FRONTEND_ORIGIN")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("FRONTEND_ORIGIN requires at least one HTTP(S) origin")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment or "*" in origin
                or any(character.isspace() for character in origin)
            ):
                raise ValueError("FRONTEND_ORIGIN must contain exact HTTP(S) origins without paths")
            parsed.port  # Validate port syntax and range.
        return ",".join(dict.fromkeys(origins))


settings = Settings()

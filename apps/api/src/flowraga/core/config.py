from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FlowRAGA API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+asyncpg://flowraga:local-development-only@localhost:5432/flowraga"
    )
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    jwt_secret: str = "local-development-secret-change-before-deployment"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "flowraga-api"
    jwt_audience: str = "flowraga-web"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    auth_cookie_secure: bool = False
    auth_cookie_domain: str | None = None
    storage_root: str = "./data/uploads"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    max_archive_uncompressed_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    max_archive_entries: int = Field(default=2000, ge=1, le=10000)

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origins(cls, origins: list[str]) -> list[str]:
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not permitted")
        return origins

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.is_production and (
            len(self.jwt_secret) < 32 or self.jwt_secret.startswith("local-development")
        ):
            raise ValueError(
                "Production JWT_SECRET must be a unique value of at least 32 characters"
            )
        if self.is_production and not self.auth_cookie_secure:
            raise ValueError("Production authentication cookies must be secure")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()

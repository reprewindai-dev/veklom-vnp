"""Canonical VNP runtime configuration.

Production startup is fail-closed: the service refuses to boot when demo
data is enabled, when no explicit CORS allowlist is configured, or when the
database is unreachable.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


DEFAULT_PRODUCTION_ORIGINS = [
    "https://veklom.com",
    "https://www.veklom.com",
    "https://vnp.veklom.com",
    "https://control.veklom.com",
    "https://veklom.dev",
]


class Settings(BaseSettings):
    """Environment-driven settings for the standalone VNP service."""

    vnp_env: str = "development"
    vnp_allow_demo_data: bool = False
    vnp_require_db: bool = True
    vnp_cors_allow_origins: str = ""
    vnp_node_heartbeat_freshness_seconds: int = 300
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/veklom",
    )
    pgl_service_url: str = os.getenv("PGL_SERVICE_URL", "http://pgl.veklom.internal")
    pgl_signing_key: str = os.getenv("PGL_SIGNING_KEY", "dev_only_unsafe_key")

    class Config:
        env_prefix = ""
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        return self.vnp_env.lower() in ("production", "prod")

    @property
    def demo_mode_active(self) -> bool:
        """Demo data may only ever be active outside production."""
        return self.vnp_allow_demo_data and not self.is_production

    @property
    def cors_origins(self) -> List[str]:
        configured = [
            origin.strip()
            for origin in self.vnp_cors_allow_origins.split(",")
            if origin.strip()
        ]
        if configured:
            return configured
        if self.is_production:
            return DEFAULT_PRODUCTION_ORIGINS
        return ["*"]

    def validate_production_startup(self) -> None:
        """Raise if this configuration is unsafe to run in production."""
        if not self.is_production:
            return
        if self.vnp_allow_demo_data:
            raise RuntimeError(
                "Refusing production startup: VNP_ALLOW_DEMO_DATA is enabled. "
                "Demo data must never run in production."
            )
        if "*" in self.cors_origins:
            raise RuntimeError(
                "Refusing production startup: wildcard CORS origin configured. "
                "Set VNP_CORS_ALLOW_ORIGINS to an explicit allowlist."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()

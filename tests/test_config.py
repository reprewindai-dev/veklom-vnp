"""Production configuration must fail closed."""
import pytest

from app.core.config import Settings, DEFAULT_PRODUCTION_ORIGINS


def test_demo_data_default_off():
    settings = Settings(vnp_env="development")
    assert settings.vnp_allow_demo_data is False
    assert settings.demo_mode_active is False


def test_demo_mode_never_active_in_production():
    settings = Settings(vnp_env="production", vnp_allow_demo_data=True)
    assert settings.demo_mode_active is False


def test_production_startup_refuses_demo_data():
    settings = Settings(vnp_env="production", vnp_allow_demo_data=True)
    with pytest.raises(RuntimeError, match="VNP_ALLOW_DEMO_DATA"):
        settings.validate_production_startup()


def test_production_startup_refuses_wildcard_cors():
    settings = Settings(vnp_env="production", vnp_cors_allow_origins="*")
    with pytest.raises(RuntimeError, match="wildcard CORS"):
        settings.validate_production_startup()


def test_production_default_cors_is_explicit_allowlist():
    settings = Settings(vnp_env="production")
    assert settings.cors_origins == DEFAULT_PRODUCTION_ORIGINS
    assert "*" not in settings.cors_origins
    settings.validate_production_startup()


def test_development_startup_allows_demo_data():
    settings = Settings(vnp_env="development", vnp_allow_demo_data=True)
    assert settings.demo_mode_active is True
    settings.validate_production_startup()

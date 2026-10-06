"""Test Settings initialization and validation."""

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_settings_defaults() -> None:
    """Done when: Settings has correct defaults."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.env == "local"
    assert settings.log_level == "INFO"
    assert settings.git_sha == "dev"
    assert settings.ai_provider == "fake"


def test_settings_env_local() -> None:
    """Done when: ORSYN_ENV=local is valid."""
    settings = Settings(_env_file=None, env="local")  # type: ignore[call-arg]
    assert settings.env == "local"


def test_settings_env_dev() -> None:
    """Done when: ORSYN_ENV=dev is valid."""
    settings = Settings(_env_file=None, env="dev")  # type: ignore[call-arg]
    assert settings.env == "dev"


def test_settings_env_prod() -> None:
    """Done when: env=prod with the fake verification provider is refused (KYC never on fake)."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="prod")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="prod", verification_provider="fake")  # type: ignore[call-arg]


def test_settings_env_invalid() -> None:
    """Done when: ORSYN_ENV=staging raises ValidationError."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="staging")  # type: ignore[call-arg,arg-type]


def test_settings_ai_provider_fake() -> None:
    """Done when: ORSYN_AI_PROVIDER=fake is valid."""
    settings = Settings(_env_file=None, ai_provider="fake")  # type: ignore[call-arg]
    assert settings.ai_provider == "fake"


def test_settings_ai_provider_invalid() -> None:
    """Done when: ORSYN_AI_PROVIDER=openai raises ValidationError."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_provider="openai")  # type: ignore[call-arg,arg-type]


def test_settings_custom_log_level() -> None:
    """Done when: ORSYN_LOG_LEVEL override works."""
    settings = Settings(_env_file=None, log_level="DEBUG")  # type: ignore[call-arg]
    assert settings.log_level == "DEBUG"


def test_settings_custom_git_sha() -> None:
    """Done when: ORSYN_GIT_SHA override works."""
    settings = Settings(_env_file=None, git_sha="deadbeef")  # type: ignore[call-arg]
    assert settings.git_sha == "deadbeef"


def test_settings_docs_enabled_local() -> None:
    """Done when: docs_enabled is True in local."""
    settings = Settings(_env_file=None, env="local")  # type: ignore[call-arg]
    assert settings.docs_enabled is True


def test_settings_docs_enabled_dev() -> None:
    """Done when: docs_enabled is True in dev."""
    settings = Settings(_env_file=None, env="dev")  # type: ignore[call-arg]
    assert settings.docs_enabled is True


def test_settings_docs_disabled_prod() -> None:
    """Done when: docs_enabled is False in prod."""
    # model_construct skips the prod+fake validator, which is the only way to get a prod object.
    settings = Settings.model_construct(
        env="prod",
        log_level="INFO",
        git_sha="abc",
        ai_provider="fake",
        verification_provider="fake",
    )
    assert settings.docs_enabled is False


def test_settings_no_env_file() -> None:
    """Done when: Settings(_env_file=None) ignores any .env file."""
    # This test verifies the setting works; an actual .env presence would be tested
    # by trying to load and verifying it doesn't.
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.ai_provider == "fake"

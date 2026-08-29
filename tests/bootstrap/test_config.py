from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from ai_blogger.bootstrap.config import (
    MIN_ENCRYPTION_KEY_BYTES,
    ConfigurationError,
    Environment,
    PostgresSettings,
    RedisSettings,
    Settings,
    load_settings,
)

SECRET_ENV: dict[str, str] = {
    "TELEGRAM__BOT_TOKEN": "0000000:fake-bot-token-for-tests",
    "POSTGRES__PASSWORD": "fake-postgres-password",
    "LLM__ANTHROPIC_API_KEY": "fake-anthropic-key",
    "LLM__OPENAI_API_KEY": "fake-openai-key",
    "STORAGE__ACCESS_KEY_ID": "fake-access-key",
    "STORAGE__SECRET_ACCESS_KEY": "fake-secret-key",
    "SECURITY__SECRETS_ENCRYPTION_KEY": "fake-encryption-key-of-sufficient-length-0123",
}

PUBLIC_ENV: dict[str, str] = {
    "TELEGRAM__ADMIN_CHAT_ID": "-1001234567890",
    "STORAGE__ENDPOINT_URL": "https://example.invalid",
}

MINIMAL_ENV: dict[str, str] = SECRET_ENV | PUBLIC_ENV


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for key, value in MINIMAL_ENV.items():
        monkeypatch.setenv(key, value)

    return dict(MINIMAL_ENV)


def test_settings_are_read_from_environment(env: dict[str, str]) -> None:
    """Секции собираются из переменных с двойным подчёркиванием"""
    settings = Settings(_env_file=None)

    assert settings.environment is Environment.LOCAL
    assert settings.telegram.admin_chat_id == -1001234567890
    assert settings.telegram.bot_token.get_secret_value() == env["TELEGRAM__BOT_TOKEN"]
    assert settings.redis.port == 6379
    assert settings.llm.draft_model == "claude-sonnet-5"


@pytest.mark.usefixtures("env")
def test_secrets_never_appear_in_repr() -> None:
    settings = Settings(_env_file=None)
    dump = f"{settings!r} {settings!s}"

    for name, secret in SECRET_ENV.items():
        assert secret not in dump, f"значение {name} видно в логах"


def test_dsn_carries_password_and_safe_dsn_does_not() -> None:
    postgres = PostgresSettings(password=SecretStr("p@ss/word"), host="db")

    assert "p%40ss%2Fword" in postgres.dsn
    assert postgres.safe_dsn == "postgresql+asyncpg://ai_blogger:***@db:5432/ai_blogger"
    assert "p@ss/word" not in postgres.safe_dsn


def test_redis_dsn_omits_credentials_when_there_is_no_password() -> None:
    assert RedisSettings().dsn == "redis://localhost:6379/0"
    assert RedisSettings(password=SecretStr("hunter2")).dsn == "redis://:hunter2@localhost:6379/0"


def test_production_rejects_debug(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("OBSERVABILITY__LOG_FORMAT", "json")

    with pytest.raises(ValidationError, match="debug=true"):
        Settings(_env_file=None)


def test_production_rejects_placeholder_secrets(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OBSERVABILITY__LOG_FORMAT", "json")
    monkeypatch.setenv("LLM__OPENAI_API_KEY", "CHANGE-ME")

    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None)

    message = str(failure.value)

    assert "llm.openai_api_key" in message
    assert "CHANGE-ME" not in message


def test_production_requires_machine_readable_logs(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(ValidationError, match="log_format"):
        Settings(_env_file=None)


def test_short_encryption_key_is_rejected_everywhere(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECURITY__SECRETS_ENCRYPTION_KEY", "short")

    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None)

    assert str(MIN_ENCRYPTION_KEY_BYTES) in str(failure.value)


def test_missing_required_secret_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM__BOT_TOKEN", raising=False)

    with pytest.raises(ValidationError, match="telegram"):
        Settings(_env_file=None)


def test_typo_in_section_field_is_not_silently_ignored(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES__PORTT", "5433")

    with pytest.raises(ValidationError, match="portt"):
        Settings(_env_file=None)


def test_empty_optional_variable_is_treated_as_unset(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM__API_ID", "")
    monkeypatch.setenv("SEARCH__API_KEY", "")
    monkeypatch.setenv("STORAGE__PUBLIC_BASE_URL", "   ")

    settings = Settings(_env_file=None)

    assert settings.telegram.api_id is None
    assert settings.search.api_key is None
    assert settings.storage.public_base_url is None


def test_empty_required_variable_reports_a_missing_field(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES__PASSWORD", "")

    with pytest.raises(ValidationError, match="password"):
        Settings(_env_file=None)


def test_load_settings_reports_the_variable_but_not_its_value(
    env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM__API_ID", "не-число")

    with pytest.raises(ConfigurationError) as failure:
        load_settings(_env_file=None)

    message = str(failure.value)

    assert "TELEGRAM__API_ID" in message

    for secret in SECRET_ENV.values():
        assert secret not in message

    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None

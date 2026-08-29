from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote_plus

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from collections.abc import Iterator

MIN_ENCRYPTION_KEY_BYTES = 32

PLACEHOLDER_SECRETS = frozenset(
    {"", "-", "change-me", "changeme", "example", "password", "secret", "test", "todo", "xxx"}
)


class ConfigurationError(Exception):
    """Приложение не может собрать конфигурацию и не должно стартовать"""


class Environment(StrEnum):
    """Окружение, в котором запущено приложение"""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self is Environment.PRODUCTION


def _unset_empty_values(data: Any) -> Any:
    if not isinstance(data, dict):
        return data

    return {
        key: value
        for key, value in data.items()
        if not (isinstance(value, str) and not value.strip())
    }


class Section(BaseModel):
    """Общий предок секций конфигурации"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _treat_empty_strings_as_unset(cls, data: Any) -> Any:
        return _unset_empty_values(data)


class TelegramSettings(Section):
    bot_token: SecretStr
    admin_chat_id: int
    api_id: int | None = None
    api_hash: SecretStr | None = None
    session_path: str = "data/telethon.session"


class PostgresSettings(Section):
    """Основное хранилище: контент-план, метрики, настройки каналов."""

    host: str = "localhost"
    port: int = 5432
    user: str = "ai_blogger"
    password: SecretStr
    database: str = "ai_blogger"
    pool_size: int = 10
    max_overflow: int = 5
    echo: bool = False

    @property
    def dsn(self) -> str:
        password = quote_plus(self.password.get_secret_value())

        return (
            f"postgresql+asyncpg://{quote_plus(self.user)}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def safe_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:***@{self.host}:{self.port}/{self.database}"


class RedisSettings(Section):
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: SecretStr | None = None

    @property
    def dsn(self) -> str:
        credentials = f":{quote_plus(self.password.get_secret_value())}@" if self.password else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"

    @property
    def safe_dsn(self) -> str:
        credentials = ":***@" if self.password else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"


class LLMSettings(Section):
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr
    deepseek_api_key: SecretStr | None = None
    draft_model: str = "claude-sonnet-5"
    critic_model: str = "gpt-5.4-nano"
    image_model: str = "gpt-image-2"
    digest_model: str = "deepseek-v4"
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=3, ge=0)


class StorageSettings(Section):
    endpoint_url: str
    access_key_id: SecretStr
    secret_access_key: SecretStr
    bucket: str = "ai-blogger-media"
    public_base_url: str | None = None


class SearchSettings(Section):
    api_key: SecretStr | None = None
    monthly_query_budget: int = Field(default=600, ge=0)


class SecuritySettings(Section):
    secrets_encryption_key: SecretStr
    admin_session_ttl_minutes: int = Field(default=720, gt=0)
    invite_max_attempts: int = Field(default=5, gt=0)

    @field_validator("secrets_encryption_key")
    @classmethod
    def _key_must_be_long_enough(cls, value: SecretStr) -> SecretStr:
        length = len(value.get_secret_value().encode())

        if length < MIN_ENCRYPTION_KEY_BYTES:
            raise ValueError(
                f"ключ шифрования короче {MIN_ENCRYPTION_KEY_BYTES} байт "
                f"(сейчас {length}); сгенерируйте новый: openssl rand -base64 48"
            )

        return value


class ObservabilitySettings(Section):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"
    metrics_enabled: bool = True
    metrics_port: int = Field(default=9090, gt=0, lt=65536)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    debug: bool = False
    telegram: TelegramSettings
    postgres: PostgresSettings
    llm: LLMSettings
    storage: StorageSettings
    security: SecuritySettings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @model_validator(mode="before")
    @classmethod
    def _treat_empty_strings_as_unset(cls, data: Any) -> Any:
        return _unset_empty_values(data)

    @model_validator(mode="after")
    def _production_must_be_configured_properly(self) -> Settings:
        if not self.environment.is_production:
            return self

        problems: list[str] = []

        if self.debug:
            problems.append("debug=true — наружу утекут трассировки и параметры запросов")

        placeholders = [
            path
            for path, secret in _iter_secrets(self)
            if secret.get_secret_value().strip().lower() in PLACEHOLDER_SECRETS
        ]
        if placeholders:
            problems.append("секреты остались шаблонными: " + ", ".join(sorted(placeholders)))

        if self.observability.log_format != "json":
            problems.append("log_format=console — такие логи не разберёт сборщик")

        if problems:
            raise ValueError("конфигурация непригодна для production: " + "; ".join(problems))

        return self


def _iter_secrets(model: BaseModel, prefix: str = "") -> Iterator[tuple[str, SecretStr]]:
    """Обходит модель вглубь и отдаёт все её секреты вместе с путём до них.

    Путь (`telegram.bot_token`) нужен, чтобы в сообщении об ошибке было
    понятно, что именно не настроено, и при этом не светилось значение.
    """
    for name, value in model:
        path = f"{prefix}{name}"
        if isinstance(value, SecretStr):
            yield path, value
        elif isinstance(value, BaseModel):
            yield from _iter_secrets(value, f"{path}.")


def _describe(error: ValidationError) -> str:
    lines = []

    for item in error.errors():
        variable = "__".join(str(part) for part in item["loc"]).upper()
        lines.append(f"  {variable or '<конфигурация в целом>'}: {item['msg']}")

    return "не удалось собрать конфигурацию:\n" + "\n".join(lines)


def load_settings(**overrides: Any) -> Settings:
    try:
        return Settings(**overrides)

    except ValidationError as error:
        problem = _describe(error)

    raise ConfigurationError(problem)

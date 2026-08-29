from __future__ import annotations

import logging
import re
import sys
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog
from pydantic import SecretStr

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping
    from contextlib import AbstractContextManager
    from contextvars import Token
    from types import TracebackType
    from typing import TextIO

LogFormat = Literal["console", "json"]

MASK: Final = "***"

SECRET_NAME_WORDS: Final = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "passwd",
        "password",
        "pwd",
        "secret",
        "secrets",
        "token",
    }
)

KEY_QUALIFIERS: Final = frozenset({"access", "api", "encryption", "private", "secret", "signing"})
NAME_SEPARATORS: Final = re.compile(r"[^a-z0-9]+")
SECRET_VALUE_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{30,}"), MASK),
    (re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}"), MASK),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]{16,}=*"), r"\1" + MASK),
    (re.compile(r"(?i)([a-z0-9+.-]+://[^:@/\s]+:)[^@/\s]+(@)"), r"\1" + MASK + r"\2"),
)

NOISY_LOGGERS: Final = (
    "asyncio",
    "botocore",
    "httpcore",
    "httpx",
    "sqlalchemy.engine",
    "telethon.network",
    "urllib3",
)


def _scrub_text(value: str) -> str:
    """Вырезает из строки всё, что похоже на секрет"""
    for pattern, replacement in SECRET_VALUE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _looks_secret(name: object) -> bool:
    if not isinstance(name, str):
        return False

    words = [word for word in NAME_SEPARATORS.split(name.lower()) if word]

    if any(word in SECRET_NAME_WORDS for word in words):
        return True

    return any(
        current == "key" and previous in KEY_QUALIFIERS for previous, current in pairwise(words)
    )


def _mask(name: object, value: Any) -> Any:
    """Приводит одно значение к безопасному для лога виду"""
    if isinstance(value, SecretStr):
        return MASK

    if _looks_secret(name) and not isinstance(value, (bool, int, float, type(None))):
        return MASK

    if isinstance(value, str):
        return _scrub_text(value)

    if isinstance(value, dict):
        return {key: _mask(key, item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return type(value)(_mask(name, item) for item in value)

    return value


def redact_secrets(
    _logger: object,
    _method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Процессор structlog: чистит событие от секретов перед выводом.

    Стоит последним из общих обработчиков — уже после того, как контекст
    подмешан, но ещё до рендера, поэтому под чистку попадает всё событие
    целиком, включая привязанные значения.
    """
    return {key: _mask(key, value) for key, value in event_dict.items()}


def configure_logging(
    *,
    level: str = "INFO",
    log_format: LogFormat = "console",
    stream: TextIO | None = None,
) -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        redact_secrets,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *_renderers(log_format),
            ],
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, root.level))


def _renderers(log_format: LogFormat) -> list[Any]:
    if log_format == "json":
        return [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ]
    return [structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())]


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)


def log_context(**values: Any) -> AbstractContextManager[None]:
    return _LogContext(values)


class _LogContext:
    __slots__ = ("_tokens", "_values")

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)
        self._tokens: Mapping[str, Token[Any]] = {}

    def __enter__(self) -> None:
        self._tokens = structlog.contextvars.bind_contextvars(**self._values)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        structlog.contextvars.reset_contextvars(**self._tokens)

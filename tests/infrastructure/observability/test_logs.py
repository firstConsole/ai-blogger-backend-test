"""Тесты логирования"""

from __future__ import annotations

import json
import logging
from io import StringIO
from typing import TYPE_CHECKING, Any

import pytest
import structlog
from pydantic import SecretStr

from ai_blogger.infrastructure.observability.logs import (
    MASK,
    LogFormat,
    configure_logging,
    get_logger,
    log_context,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

FAKE_BOT_TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # gitleaks:allow


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level

    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        structlog.reset_defaults()
        structlog.contextvars.clear_contextvars()


@pytest.fixture
def output() -> StringIO:
    return StringIO()


def _setup(output: StringIO, log_format: LogFormat = "json") -> Any:
    configure_logging(level="DEBUG", log_format=log_format, stream=output)
    return get_logger("test")


def _last_event(output: StringIO) -> dict[str, Any]:
    lines = [line for line in output.getvalue().splitlines() if line.strip()]
    assert lines, "лог пуст — событие не дошло до вывода"
    parsed: dict[str, Any] = json.loads(lines[-1])

    return parsed


def test_json_event_carries_the_fields_a_log_collector_needs(output: StringIO) -> None:
    _setup(output).info("post_published", post_id=412)

    event = _last_event(output)

    assert event["event"] == "post_published"
    assert event["level"] == "info"
    assert event["logger"] == "test"
    assert event["post_id"] == 412
    assert event["timestamp"].endswith("Z")


def test_bot_token_inside_a_message_is_masked(output: StringIO) -> None:
    _setup(output).warning(
        f"запрос не прошёл: https://api.telegram.org/bot{FAKE_BOT_TOKEN}/sendPhoto"
    )

    event = _last_event(output)

    assert FAKE_BOT_TOKEN not in json.dumps(event, ensure_ascii=False)
    assert MASK in event["event"]
    assert "api.telegram.org" in event["event"]


def test_fields_named_like_secrets_are_masked(output: StringIO) -> None:
    """Значение поля с «секретным» именем не показываем, как бы оно ни выглядело."""
    _setup(output).info(
        "channel_configured",
        bot_token="совершенно-обычная-строка",
        openai_api_key="another-one",
        channel_title="Технологии",
    )

    event = _last_event(output)

    assert event["bot_token"] == MASK
    assert event["openai_api_key"] == MASK
    assert event["channel_title"] == "Технологии"


def test_secrets_nested_in_structures_are_masked_too(output: StringIO) -> None:
    _setup(output).info(
        "provider_call_failed",
        request={
            "model": "claude-sonnet-5",
            "headers": {"authorization": "Bearer abcdef0123456789"},
        },
        attempts=[{"password": "hunter2"}],
    )

    dumped = json.dumps(_last_event(output), ensure_ascii=False)

    assert "hunter2" not in dumped
    assert "abcdef0123456789" not in dumped
    assert "claude-sonnet-5" in dumped


def test_secret_str_is_never_unwrapped(output: StringIO) -> None:
    _setup(output).info("startup", value=SecretStr("fake-anthropic-key"))

    assert "fake-anthropic-key" not in output.getvalue()


def test_dsn_password_is_masked_but_address_survives(output: StringIO) -> None:
    _setup(output).error(
        "db_unavailable", dsn="postgresql+asyncpg://ai_blogger:s3cret@db:5432/main"
    )

    event = _last_event(output)

    assert "s3cret" not in event["dsn"]
    assert event["dsn"] == f"postgresql+asyncpg://ai_blogger:{MASK}@db:5432/main"


def test_records_from_standard_logging_are_redacted_as_well(output: StringIO) -> None:
    _setup(output)

    logging.getLogger("some_library.client").warning(
        "GET https://api.telegram.org/bot%s/getUpdates", FAKE_BOT_TOKEN
    )

    assert FAKE_BOT_TOKEN not in output.getvalue()
    assert MASK in _last_event(output)["event"]


def test_log_context_attaches_to_every_record_inside_the_block(output: StringIO) -> None:
    logger = _setup(output)

    with log_context(post_id=412, channel="tech"):
        logger.info("image_generated")
    logger.info("worker_idle")

    events = [json.loads(line) for line in output.getvalue().splitlines() if line.strip()]

    assert events[0]["post_id"] == 412
    assert events[0]["channel"] == "tech"
    assert "post_id" not in events[1]


def test_nested_log_context_restores_the_outer_value(output: StringIO) -> None:
    logger = _setup(output)

    with log_context(stage="draft"):
        with log_context(stage="critic"):
            logger.info("inner")
        logger.info("outer")

    events = [json.loads(line) for line in output.getvalue().splitlines() if line.strip()]

    assert events[0]["stage"] == "critic"
    assert events[1]["stage"] == "draft"


def test_console_format_stays_readable_for_humans(output: StringIO) -> None:
    _setup(output, log_format="console").info("post_published", post_id=412)

    written = output.getvalue()

    assert "post_published" in written
    assert "post_id=412" in written
    assert not written.lstrip().startswith("{")


def test_token_counters_are_not_mistaken_for_secrets(output: StringIO) -> None:
    _setup(output).info(
        "draft_generated",
        tokens_in=15_000,
        tokens_out=2_500,
        token_count=17_500,
        cache_key="topic:412",
        bot_token="этот замазать",
    )

    event = _last_event(output)

    assert event["tokens_in"] == 15_000
    assert event["tokens_out"] == 2_500
    assert event["token_count"] == 17_500
    assert event["cache_key"] == "topic:412"
    assert event["bot_token"] == MASK


def test_header_style_names_are_recognised(output: StringIO) -> None:
    _setup(output).info("request", headers={"X-Api-Key": "abc", "X-Request-Id": "r-1"})

    headers = _last_event(output)["headers"]

    assert headers["X-Api-Key"] == MASK
    assert headers["X-Request-Id"] == "r-1"

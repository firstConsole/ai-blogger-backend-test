"""Тесты канала"""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from ai_blogger.domain.entities.channel import MAX_TITLE_LENGTH, Channel
from ai_blogger.domain.errors import ChannelPausedError, InvalidValueError
from ai_blogger.domain.values.editorial import EditorialPolicy
from ai_blogger.domain.values.identifiers import ChannelId
from ai_blogger.domain.values.language import Language
from ai_blogger.domain.values.schedule import PublicationSchedule
from ai_blogger.domain.values.telegram import TelegramChatId

BERLIN = ZoneInfo("Europe/Berlin")


def make_channel(title: str = "Технологии") -> Channel:
    return Channel.create(
        chat_id=TelegramChatId(-1001234567890),
        title=title,
        schedule=PublicationSchedule.of("Europe/Berlin", [time(9, 0), time(18, 0)]),
        policy=EditorialPolicy.of(
            language=Language("ru"),
            tone="спокойно, без восклицательных знаков",
            min_body_length=300,
            max_body_length=900,
        ),
    )


def test_created_channel_gets_an_identifier_and_a_trimmed_title() -> None:
    channel = make_channel("  Технологии  ")

    assert isinstance(channel.id, ChannelId)
    assert channel.title == "Технологии"
    assert channel.is_active


def test_channels_are_compared_by_identity_not_by_content() -> None:
    channel = make_channel()
    same_channel_read_again = make_channel()
    same_channel_read_again.id = channel.id
    same_channel_read_again.title = "Название успели поменять"

    assert channel == same_channel_read_again
    assert len({channel, same_channel_read_again}) == 1


def test_different_channels_are_not_equal_even_with_identical_settings() -> None:
    assert make_channel() != make_channel()


def test_comparison_with_a_stranger_does_not_explode() -> None:
    assert make_channel() != "не канал"


def test_rename_validates_the_new_title() -> None:
    channel = make_channel()

    channel.rename("  Новое имя  ")
    assert channel.title == "Новое имя"

    with pytest.raises(InvalidValueError, match="должно быть название"):
        channel.rename("   ")


def test_title_longer_than_telegram_allows_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match=str(MAX_TITLE_LENGTH)):
        make_channel("я" * (MAX_TITLE_LENGTH + 1))


def test_next_publication_comes_from_the_channel_schedule() -> None:
    channel = make_channel()

    following = channel.next_publication_after(datetime(2026, 5, 1, 10, 0, tzinfo=UTC))

    assert following == datetime(2026, 5, 1, 18, 0, tzinfo=BERLIN)


def test_paused_channel_refuses_to_name_a_publication_time() -> None:
    channel = make_channel()
    channel.pause()

    with pytest.raises(ChannelPausedError, match="остановлен"):
        channel.next_publication_after(datetime(2026, 5, 1, 10, 0, tzinfo=UTC))

    channel.resume()
    assert channel.next_publication_after(datetime(2026, 5, 1, 10, 0, tzinfo=UTC))


def test_schedule_and_policy_are_replaceable_without_touching_identity() -> None:
    """Владелец меняет настройки из бота, канал при этом остаётся тем же"""
    channel = make_channel()
    original_id = channel.id

    channel.reschedule(PublicationSchedule.of("Asia/Almaty", [time(7, 30)]))
    channel.apply_policy(
        EditorialPolicy.of(
            language=Language("kk"),
            tone="коротко и по делу",
            min_body_length=100,
            max_body_length=400,
            requires_image=False,
        )
    )

    assert channel.id == original_id
    assert channel.schedule.posts_per_week == 7
    assert channel.policy.language == Language("kk")

"""Тесты редполитики канала"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.editorial import (
    CAPTION_LIMIT,
    MAX_TAGS,
    MAX_TONE_LENGTH,
    MESSAGE_LIMIT,
    EditorialPolicy,
)
from ai_blogger.domain.values.language import Language

RUSSIAN = Language("ru")


def policy(**overrides: object) -> EditorialPolicy:
    """Рабочая политика, в которой меняют по одному полю за раз"""
    defaults: dict[str, object] = {
        "language": RUSSIAN,
        "tone": "спокойно, без восклицательных знаков",
        "min_body_length": 300,
        "max_body_length": 900,
        "min_tags": 2,
        "max_tags": 5,
        "banned_topics": (),
        "requires_image": True,
    }
    return EditorialPolicy.of(**(defaults | overrides))  # type: ignore[arg-type]


def test_of_normalizes_tone_and_bans() -> None:
    built = policy(tone="  Сдержанно  ", banned_topics=[" Политика ", "КРИПТА", "", "   "])

    assert built.tone == "Сдержанно"
    assert built.banned_topics == frozenset({"политика", "крипта"})


def test_constructor_refuses_unnormalized_ban() -> None:
    """Собрать политику в обход of не выйдет"""
    with pytest.raises(InvalidValueError, match="нормализован"):
        EditorialPolicy(
            language=RUSSIAN,
            tone="спокойно",
            min_body_length=100,
            max_body_length=900,
            min_tags=0,
            max_tags=5,
            banned_topics=frozenset({"Политика"}),
            requires_image=False,
        )


@pytest.mark.parametrize("tone", ["", "   "])
def test_empty_tone_is_rejected(tone: str) -> None:
    with pytest.raises(InvalidValueError, match="тон канала"):
        policy(tone=tone)


def test_tone_longer_than_the_limit_is_rejected() -> None:
    """Тон уезжает в каждый промпт, место там дорогое"""
    with pytest.raises(InvalidValueError, match="промпт"):
        policy(tone="а" * (MAX_TONE_LENGTH + 1))


def test_reversed_length_range_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="больше максимальной"):
        policy(min_body_length=900, max_body_length=300)


def test_post_longer_than_telegram_allows_is_rejected() -> None:
    """Политику, которую Telegram заведомо не исполнит, лучше не сохранять"""
    with pytest.raises(InvalidValueError, match=str(MESSAGE_LIMIT)):
        policy(max_body_length=MESSAGE_LIMIT + 1)


def test_reversed_tag_range_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="больше максимума"):
        policy(min_tags=5, max_tags=2)


def test_too_many_tags_read_as_spam() -> None:
    with pytest.raises(InvalidValueError, match="спам"):
        policy(max_tags=MAX_TAGS + 1)


def test_channel_with_images_is_limited_by_the_caption_not_the_message() -> None:
    """Подпись к фото жёстче обычного сообщения — об этом лучше знать заранее"""
    assert policy(requires_image=True, max_body_length=CAPTION_LIMIT).fits_single_telegram_message
    assert not policy(
        requires_image=True, max_body_length=CAPTION_LIMIT + 1
    ).fits_single_telegram_message


def test_channel_without_images_gets_the_full_message_limit() -> None:
    assert policy(
        requires_image=False, max_body_length=CAPTION_LIMIT + 1
    ).fits_single_telegram_message


@pytest.mark.parametrize(
    ("length", "accepted"), [(299, False), (300, True), (900, True), (901, False)]
)
def test_body_length_bounds_are_inclusive(length: int, accepted: bool) -> None:
    assert policy().accepts_body_length(length) is accepted


@pytest.mark.parametrize(("count", "accepted"), [(1, False), (2, True), (5, True), (6, False)])
def test_tag_count_bounds_are_inclusive(count: int, accepted: bool) -> None:
    assert policy().accepts_tag_count(count) is accepted

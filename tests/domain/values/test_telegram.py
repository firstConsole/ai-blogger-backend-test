"""Тесты адресов Telegram"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.telegram import TelegramChatId, TelegramMessageId


def test_negative_chat_id_is_normal_for_channels() -> None:
    chat = TelegramChatId(-1001234567890)

    assert chat.is_broadcast
    assert str(chat) == "-1001234567890"


def test_positive_chat_id_is_a_private_conversation() -> None:
    assert not TelegramChatId(123456789).is_broadcast


def test_zero_chat_id_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="нулём"):
        TelegramChatId(0)


@pytest.mark.parametrize("value", [0, -1])
def test_message_number_must_be_positive(value: int) -> None:
    with pytest.raises(InvalidValueError, match="положительным"):
        TelegramMessageId(value)


def test_message_number_is_kept_as_is() -> None:
    assert str(TelegramMessageId(42)) == "42"

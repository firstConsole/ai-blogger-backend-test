"""Адреса Telegram"""

from __future__ import annotations

from dataclasses import dataclass

from ai_blogger.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class TelegramChatId:
    """Идентификатор чата или канала"""

    value: int

    def __post_init__(self) -> None:
        if self.value == 0:
            raise InvalidValueError("идентификатор чата не может быть нулём")

    @property
    def is_broadcast(self) -> bool:
        """Канал или супергруппа, а не личная переписка"""
        return self.value < 0

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TelegramMessageId:
    """Номер сообщения внутри чата"""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidValueError(
                f"номер сообщения должен быть положительным, получено {self.value}"
            )

    def __str__(self) -> str:
        return str(self.value)

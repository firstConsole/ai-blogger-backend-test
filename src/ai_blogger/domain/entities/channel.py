"""Канал, который ведёт блогер"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import ChannelPausedError, InvalidValueError
from ai_blogger.domain.values.identifiers import ChannelId

if TYPE_CHECKING:
    from datetime import datetime

    from ai_blogger.domain.values.editorial import EditorialPolicy
    from ai_blogger.domain.values.schedule import PublicationSchedule
    from ai_blogger.domain.values.telegram import TelegramChatId

MAX_TITLE_LENGTH = 128


@dataclass(eq=False, slots=True)
class Channel:
    id: ChannelId
    chat_id: TelegramChatId
    title: str
    schedule: PublicationSchedule
    policy: EditorialPolicy
    is_active: bool = True

    def __post_init__(self) -> None:
        _check_title(self.title)

    @classmethod
    def create(
        cls,
        *,
        chat_id: TelegramChatId,
        title: str,
        schedule: PublicationSchedule,
        policy: EditorialPolicy,
    ) -> Self:
        """Завести новый канал"""
        return cls(
            id=ChannelId.new(),
            chat_id=chat_id,
            title=title.strip(),
            schedule=schedule,
            policy=policy,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Channel):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def rename(self, title: str) -> None:
        """Переименовать канал"""
        stripped = title.strip()
        _check_title(stripped)
        self.title = stripped

    def reschedule(self, schedule: PublicationSchedule) -> None:
        """Заменить расписание публикаций"""
        self.schedule = schedule

    def apply_policy(self, policy: EditorialPolicy) -> None:
        """Заменить редполитику"""
        self.policy = policy

    def pause(self) -> None:
        """Остановить канал: посты копятся, но не выходят"""
        self.is_active = False

    def resume(self) -> None:
        """Вернуть канал в работу"""
        self.is_active = True

    def next_publication_after(self, moment: datetime) -> datetime:
        """Когда канал выпустит следующий пост"""
        if not self.is_active:
            raise ChannelPausedError(f"канал «{self.title}» остановлен, расписание не работает")
        return self.schedule.next_slot_after(moment)


def _check_title(title: str) -> None:
    if not title:
        raise InvalidValueError("у канала должно быть название")
    if title != title.strip():
        raise InvalidValueError("название канала не должно начинаться или кончаться пробелами")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidValueError(
            f"Telegram не примет название длиннее {MAX_TITLE_LENGTH} символов, "
            f"получено {len(title)}"
        )

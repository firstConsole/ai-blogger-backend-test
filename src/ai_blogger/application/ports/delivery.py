"""Порты публикации, хранения медиа и сбора показателей"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ai_blogger.domain.entities.channel import Channel
    from ai_blogger.domain.entities.post import Post
    from ai_blogger.domain.values.identifiers import MediaId
    from ai_blogger.domain.values.telegram import TelegramChatId, TelegramMessageId

    from .content import DrawnImage


@dataclass(frozen=True, slots=True)
class Measurement:
    """Показатели поста, снятые снаружи"""

    views: int
    forwards: int
    reactions: int


class MediaStorage(Protocol):
    """Объектное хранилище картинок"""

    async def put(self, image: DrawnImage) -> MediaId:
        """Положить картинку и вернуть её идентификатор"""
        ...

    async def public_url(self, media_id: MediaId) -> str:
        """Ссылка, по которой картинку заберёт Telegram"""
        ...


class Publisher(Protocol):
    """Отправка поста в канал"""

    async def publish(
        self, *, channel: Channel, post: Post, image_url: str | None
    ) -> TelegramMessageId:
        """Опубликовать пост и вернуть номер получившегося сообщения"""
        ...


class AudienceMetrics(Protocol):
    """Сбор показателей опубликованного поста"""

    async def measure(
        self, *, chat_id: TelegramChatId, message_id: TelegramMessageId
    ) -> Measurement:
        """Снять текущие показатели сообщения"""
        ...

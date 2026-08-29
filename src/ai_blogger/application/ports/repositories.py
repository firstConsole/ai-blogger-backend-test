"""Репозитории: хранение сущностей на языке сценария"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from ai_blogger.domain.entities.channel import Channel
    from ai_blogger.domain.entities.metrics import PostMetrics
    from ai_blogger.domain.entities.post import Post
    from ai_blogger.domain.entities.topic import Topic
    from ai_blogger.domain.values.identifiers import ChannelId, PostId, TopicId
    from ai_blogger.domain.values.post_status import PostStatus
    from ai_blogger.domain.values.telegram import TelegramChatId


class ChannelRepository(Protocol):
    """Каналы, которые ведёт блогер"""

    async def get(self, channel_id: ChannelId) -> Channel | None:
        """Найти канал по идентификатору"""
        ...

    async def get_by_chat(self, chat_id: TelegramChatId) -> Channel | None:
        """Найти канал по чату — так его узнаёт бот, получив сообщение"""
        ...

    async def active(self) -> Sequence[Channel]:
        """Каналы в работе; остановленные планировщику не нужны"""
        ...

    async def save(self, channel: Channel) -> None:
        """Сохранить канал"""
        ...


class TopicRepository(Protocol):
    """Найденные темы"""

    async def get(self, topic_id: TopicId) -> Topic | None:
        """Найти тему по идентификатору"""
        ...

    async def discovered_since(self, channel_id: ChannelId, since: datetime) -> Sequence[Topic]:
        """Темы канала за окно дедупликации"""
        ...

    async def save(self, topic: Topic) -> None:
        """Сохранить тему"""
        ...


class PostRepository(Protocol):
    """Посты на всех стадиях"""

    async def get(self, post_id: PostId) -> Post | None:
        """Найти пост по идентификатору"""
        ...

    async def with_status(self, channel_id: ChannelId, status: PostStatus) -> Sequence[Post]:
        """Посты канала в заданном состоянии — этим живёт админ-чат"""
        ...

    async def due_for_publication(self, moment: datetime) -> Sequence[Post]:
        """Одобренные посты, чьё время пришло"""
        ...

    async def save(self, post: Post) -> None:
        """Сохранить пост"""
        ...


class PostMetricsRepository(Protocol):
    """История показателей опубликованных постов"""

    async def get(self, post_id: PostId) -> PostMetrics | None:
        """История конкретного поста"""
        ...

    async def due_for_measurement(self, moment: datetime) -> Sequence[PostMetrics]:
        """Посты, у которых подошёл очередной замер"""
        ...

    async def save(self, metrics: PostMetrics) -> None:
        """Сохранить историю"""
        ...

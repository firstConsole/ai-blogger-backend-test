"""Реализации портов в памяти

Живут в тестах намеренно. Сценариям всё равно, что стоит за портом, и пока
настоящей базы нет, проверять их удобнее на этих. Заодно это первая проверка
самих портов: если фейк разойдётся с протоколом хоть в одном аргументе,
упадёт mypy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from types import TracebackType

    from ai_blogger.domain.entities.channel import Channel
    from ai_blogger.domain.entities.metrics import PostMetrics
    from ai_blogger.domain.entities.post import Post
    from ai_blogger.domain.entities.topic import Topic
    from ai_blogger.domain.values.identifiers import ChannelId, PostId, TopicId
    from ai_blogger.domain.values.post_status import PostStatus
    from ai_blogger.domain.values.telegram import TelegramChatId


class FixedClock:
    """Часы, которые стоят там, где их поставили"""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def move_to(self, moment: datetime) -> None:
        self._moment = moment


class InMemoryUnitOfWork:
    """Транзакция, которая только считает, сколько раз её зафиксировали"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class InMemoryChannelRepository:
    """Каналы в словаре"""

    def __init__(self) -> None:
        self.items: dict[ChannelId, Channel] = {}

    async def get(self, channel_id: ChannelId) -> Channel | None:
        return self.items.get(channel_id)

    async def get_by_chat(self, chat_id: TelegramChatId) -> Channel | None:
        return next(
            (channel for channel in self.items.values() if channel.chat_id == chat_id), None
        )

    async def active(self) -> Sequence[Channel]:
        return [channel for channel in self.items.values() if channel.is_active]

    async def save(self, channel: Channel) -> None:
        self.items[channel.id] = channel


class InMemoryTopicRepository:
    """Темы в словаре"""

    def __init__(self) -> None:
        self.items: dict[TopicId, Topic] = {}

    async def get(self, topic_id: TopicId) -> Topic | None:
        return self.items.get(topic_id)

    async def discovered_since(self, channel_id: ChannelId, since: datetime) -> Sequence[Topic]:
        return [
            topic
            for topic in self.items.values()
            if topic.channel_id == channel_id and topic.discovered_at >= since
        ]

    async def save(self, topic: Topic) -> None:
        self.items[topic.id] = topic


class InMemoryPostRepository:
    """Посты в словаре"""

    def __init__(self) -> None:
        self.items: dict[PostId, Post] = {}

    async def get(self, post_id: PostId) -> Post | None:
        return self.items.get(post_id)

    async def with_status(self, channel_id: ChannelId, status: PostStatus) -> Sequence[Post]:
        return [
            post
            for post in self.items.values()
            if post.channel_id == channel_id and post.status is status
        ]

    async def due_for_publication(self, moment: datetime) -> Sequence[Post]:
        return [post for post in self.items.values() if post.is_due(moment)]

    async def save(self, post: Post) -> None:
        self.items[post.id] = post


class InMemoryPostMetricsRepository:
    """История показателей в словаре"""

    def __init__(self) -> None:
        self.items: dict[PostId, PostMetrics] = {}

    async def get(self, post_id: PostId) -> PostMetrics | None:
        return self.items.get(post_id)

    async def due_for_measurement(self, moment: datetime) -> Sequence[PostMetrics]:
        return [
            metrics
            for metrics in self.items.values()
            if metrics.next_due_at is not None and metrics.next_due_at <= moment
        ]

    async def save(self, metrics: PostMetrics) -> None:
        self.items[metrics.post_id] = metrics

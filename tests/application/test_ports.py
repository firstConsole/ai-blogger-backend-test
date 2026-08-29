"""Тесты портов

У протокола нет поведения, поэтому проверять здесь нужно две вещи: что
реализация действительно подходит под порт и что порт описывает то, что
сценариям понадобится. Первое делает mypy на присваиваниях ниже, второе —
обычные тесты на фейках.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING

from ai_blogger.domain.entities.channel import Channel
from ai_blogger.domain.entities.metrics import PostMetrics
from ai_blogger.domain.entities.post import Post
from ai_blogger.domain.entities.topic import Topic
from ai_blogger.domain.values.editorial import EditorialPolicy
from ai_blogger.domain.values.embeddings import DEDUPLICATION_WINDOW, Embedding
from ai_blogger.domain.values.identifiers import ChannelId, PostId, TopicId
from ai_blogger.domain.values.language import Language
from ai_blogger.domain.values.post_status import PostStatus
from ai_blogger.domain.values.schedule import PublicationSchedule
from ai_blogger.domain.values.sources import SourceUrl, TopicOrigin
from ai_blogger.domain.values.telegram import TelegramChatId, TelegramUserId
from tests.application.fakes import (
    FixedClock,
    InMemoryChannelRepository,
    InMemoryPostMetricsRepository,
    InMemoryPostRepository,
    InMemoryTopicRepository,
    InMemoryUnitOfWork,
)

if TYPE_CHECKING:
    from ai_blogger.application.ports.clock import Clock
    from ai_blogger.application.ports.repositories import (
        ChannelRepository,
        PostMetricsRepository,
        PostRepository,
        TopicRepository,
    )
    from ai_blogger.application.ports.unit_of_work import UnitOfWork

NOW = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def make_channel(*, chat: int = -1001, active: bool = True) -> Channel:
    channel = Channel.create(
        chat_id=TelegramChatId(chat),
        title="Технологии",
        schedule=PublicationSchedule.of("Europe/Berlin", [time(18, 0)]),
        policy=EditorialPolicy.of(
            language=Language("ru"),
            tone="спокойно",
            min_body_length=100,
            max_body_length=900,
        ),
    )
    if not active:
        channel.pause()
    return channel


async def test_fakes_satisfy_the_ports() -> None:
    """Настоящую проверку делает mypy на этих присваиваниях

    Разойдись фейк с протоколом хоть в одном аргументе — упадёт проверка
    типов, а не тест. Вызовы ниже нужны, чтобы обращение шло через тип порта,
    а не через фейк: так проверяется ровно то, что увидит сценарий.
    """
    clock: Clock = FixedClock(NOW)
    channels: ChannelRepository = InMemoryChannelRepository()
    topics: TopicRepository = InMemoryTopicRepository()
    posts: PostRepository = InMemoryPostRepository()
    metrics: PostMetricsRepository = InMemoryPostMetricsRepository()
    transaction: UnitOfWork = InMemoryUnitOfWork()

    assert clock.now() == NOW
    assert await channels.active() == []
    assert await topics.discovered_since(ChannelId.new(), NOW) == []
    assert await posts.due_for_publication(NOW) == []
    assert await metrics.due_for_measurement(NOW) == []

    async with transaction:
        await transaction.commit()


async def test_scheduler_asks_only_for_channels_in_work() -> None:
    channels = InMemoryChannelRepository()
    await channels.save(make_channel(chat=-1001))
    await channels.save(make_channel(chat=-1002, active=False))

    assert [channel.chat_id.value for channel in await channels.active()] == [-1001]


async def test_bot_finds_the_channel_by_the_chat_it_answered_in() -> None:
    channels = InMemoryChannelRepository()
    channel = make_channel(chat=-1005)
    await channels.save(channel)

    assert await channels.get_by_chat(TelegramChatId(-1005)) == channel
    assert await channels.get_by_chat(TelegramChatId(-9999)) is None


async def test_deduplication_gets_exactly_the_window_it_asked_for() -> None:
    """Границу окна считает сценарий: домен знает её длину, но не текущее время"""
    topics = InMemoryTopicRepository()
    channel = make_channel()
    for hours in (1, 71, 73):
        await topics.save(
            Topic.discover(
                channel_id=channel.id,
                title=f"Новость {hours}",
                origin=TopicOrigin.FEED,
                discovered_at=NOW - timedelta(hours=hours),
                embedding=Embedding.of([1.0, 0.0]),
                url=SourceUrl.parse("https://news.example.com/a"),
            )
        )

    inside = await topics.discovered_since(channel.id, NOW - DEDUPLICATION_WINDOW)

    assert len(inside) == 2


async def test_publisher_gets_only_posts_whose_time_has_come() -> None:
    posts = InMemoryPostRepository()
    channel = make_channel()
    for offset in (-timedelta(minutes=1), timedelta(minutes=1)):
        post = Post.draft(
            channel_id=channel.id,
            topic_id=TopicId.new(),
            body="Достаточно длинный текст поста. " * 5,
        )
        post.send_to_review()
        post.approve(publish_at=NOW + offset, reviewed_by=TelegramUserId(1))
        await posts.save(post)

    due = await posts.due_for_publication(NOW)

    assert len(due) == 1
    assert due[0].publish_at == NOW - timedelta(minutes=1)


async def test_admin_chat_asks_for_posts_awaiting_a_decision() -> None:
    posts = InMemoryPostRepository()
    channel = make_channel()
    waiting = Post.draft(channel_id=channel.id, topic_id=TopicId.new(), body="Текст поста. " * 10)
    waiting.send_to_review()
    await posts.save(waiting)
    await posts.save(
        Post.draft(channel_id=channel.id, topic_id=TopicId.new(), body="Черновик. " * 10)
    )

    assert await posts.with_status(channel.id, PostStatus.NEEDS_REVIEW) == [waiting]


async def test_collector_asks_for_posts_whose_measurement_is_due() -> None:
    store = InMemoryPostMetricsRepository()
    fresh = PostMetrics.start(post_id=PostId.new(), published_at=NOW)
    old = PostMetrics.start(post_id=PostId.new(), published_at=NOW - timedelta(hours=2))
    await store.save(fresh)
    await store.save(old)

    due = await store.due_for_measurement(NOW)

    assert [metrics.post_id for metrics in due] == [old.post_id]

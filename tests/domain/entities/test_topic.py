"""Тесты темы"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_blogger.domain.entities.topic import MAX_TITLE_LENGTH, Topic
from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.embeddings import DEDUPLICATION_WINDOW, Embedding
from ai_blogger.domain.values.identifiers import ChannelId, TopicId
from ai_blogger.domain.values.sources import SourceUrl, TopicOrigin

FOUND_AT = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
CHANNEL = ChannelId.new()

ABOUT_NEURAL_NETWORKS = Embedding.of([1.0, 0.05, 0.0])
ALSO_ABOUT_NEURAL_NETWORKS = Embedding.of([1.0, 0.1, 0.0])
ABOUT_SOMETHING_ELSE = Embedding.of([0.0, 0.0, 1.0])


def make_topic(
    *,
    channel_id: ChannelId = CHANNEL,
    title: str = "Нейросети научились считать",
    origin: TopicOrigin = TopicOrigin.FEED,
    discovered_at: datetime = FOUND_AT,
    embedding: Embedding = ABOUT_NEURAL_NETWORKS,
    url: SourceUrl | None = None,
) -> Topic:
    return Topic.discover(
        channel_id=channel_id,
        title=title,
        origin=origin,
        discovered_at=discovered_at,
        embedding=embedding,
        url=url if url is not None else SourceUrl.parse("https://news.example.com/a"),
    )


def test_discovered_topic_gets_an_identifier_and_a_clean_title() -> None:
    """Заголовки из лент приходят с переносами строк"""
    topic = make_topic(title="  Нейросети\n  научились   считать ")

    assert isinstance(topic.id, TopicId)
    assert topic.title == "Нейросети научились считать"


def test_topics_are_compared_by_identity() -> None:
    topic = make_topic()
    same = make_topic()
    same.id = topic.id

    assert topic == same
    assert len({topic, same}) == 1
    assert make_topic() != make_topic()


def test_time_without_a_timezone_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="без часового пояса"):
        make_topic(discovered_at=datetime(2026, 5, 1, 12, 0))  # noqa: DTZ001


@pytest.mark.parametrize("origin", [TopicOrigin.FEED, TopicOrigin.SEARCH])
def test_found_topic_must_point_at_its_source(origin: TopicOrigin) -> None:
    """Пост будет ссылаться на первоисточник, значит он обязан быть"""
    with pytest.raises(InvalidValueError, match="первоисточник"):
        Topic.discover(
            channel_id=CHANNEL,
            title="Нейросети научились считать",
            origin=origin,
            discovered_at=FOUND_AT,
            embedding=ABOUT_NEURAL_NETWORKS,
        )


def test_manual_topic_may_have_no_link() -> None:
    """Владелец канала вправе просто сказать, о чём написать"""
    topic = Topic.discover(
        channel_id=CHANNEL,
        title="Разобрать новый закон о персональных данных",
        origin=TopicOrigin.MANUAL,
        discovered_at=FOUND_AT,
        embedding=ABOUT_NEURAL_NETWORKS,
    )

    assert topic.url is None


@pytest.mark.parametrize("title", ["", "   "])
def test_empty_title_is_refused(title: str) -> None:
    with pytest.raises(InvalidValueError, match="должен быть заголовок"):
        make_topic(title=title)


def test_overlong_title_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="уже не заголовок"):
        make_topic(title="а" * (MAX_TITLE_LENGTH + 1))


def test_close_titles_within_the_window_are_one_topic() -> None:
    first = make_topic(embedding=ABOUT_NEURAL_NETWORKS)
    second = make_topic(
        embedding=ALSO_ABOUT_NEURAL_NETWORKS, discovered_at=FOUND_AT + timedelta(hours=5)
    )

    assert second.is_duplicate_of(first)


def test_distant_titles_are_not_duplicates() -> None:
    first = make_topic(embedding=ABOUT_NEURAL_NETWORKS)
    second = make_topic(embedding=ABOUT_SOMETHING_ELSE)

    assert not second.is_duplicate_of(first)


def test_the_same_news_for_two_channels_stays_two_topics() -> None:
    """У каналов разная аудитория и разная редполитика"""
    ours = make_topic()
    theirs = make_topic(channel_id=ChannelId.new())

    assert not theirs.is_duplicate_of(ours)


def test_beyond_the_window_a_repeat_is_a_return_to_the_subject() -> None:
    first = make_topic()
    inside = make_topic(discovered_at=FOUND_AT + DEDUPLICATION_WINDOW)
    outside = make_topic(discovered_at=FOUND_AT + DEDUPLICATION_WINDOW + timedelta(seconds=1))

    assert inside.is_duplicate_of(first)
    assert not outside.is_duplicate_of(first)


def test_window_is_measured_between_topics_not_from_now() -> None:
    """Ответ не должен зависеть от того, когда его спросили

    Обе темы старые, между собой близки и укладываются в окно — значит,
    дубликат, сколько бы времени с тех пор ни прошло.
    """
    long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    first = make_topic(discovered_at=long_ago)
    second = make_topic(discovered_at=long_ago + timedelta(hours=1))

    assert second.is_duplicate_of(first)


def test_direction_does_not_matter() -> None:
    first = make_topic()
    second = make_topic(discovered_at=FOUND_AT + timedelta(hours=5))

    assert second.is_duplicate_of(first) == first.is_duplicate_of(second)


def test_topic_remembers_where_it_came_from() -> None:
    """Без этого непонятно, какой источник приносит темы, доходящие до канала"""
    topic = Topic.discover(
        channel_id=CHANNEL,
        title="Нейросети научились считать",
        origin=TopicOrigin.FEED,
        discovered_at=FOUND_AT,
        embedding=ABOUT_NEURAL_NETWORKS,
        url=SourceUrl.parse("https://news.example.com/a"),
        discovered_from="https://news.example.com/rss",
    )

    assert topic.discovered_from == "https://news.example.com/rss"
    assert make_topic().discovered_from is None


def test_zero_byte_in_a_feed_title_is_refused() -> None:
    """RSS с битой кодировкой приносит нулевые байты регулярно"""
    with pytest.raises(InvalidValueError, match="нулевой байт"):
        make_topic(title="Заголовок\x00с мусором")

"""Тесты истории показателей поста"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_blogger.domain.entities.metrics import PostMetrics
from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.identifiers import PostId
from ai_blogger.domain.values.metrics import MEASUREMENT_OFFSETS, MetricsSnapshot

PUBLISHED_AT = datetime(2026, 5, 1, 18, 0, tzinfo=UTC)
HOUR, FOUR_HOURS, DAY, THREE_DAYS = MEASUREMENT_OFFSETS


def snapshot(
    offset: timedelta,
    *,
    views: int = 100,
    forwards: int = 5,
    reactions: int = 10,
    late: timedelta = timedelta(),
) -> MetricsSnapshot:
    return MetricsSnapshot(
        offset=offset,
        measured_at=PUBLISHED_AT + offset + late,
        views=views,
        forwards=forwards,
        reactions=reactions,
    )


def started() -> PostMetrics:
    return PostMetrics.start(post_id=PostId.new(), published_at=PUBLISHED_AT)


def test_measurement_plan_matches_the_brief() -> None:
    """Час, четыре часа, сутки, трое суток — расписание из ТЗ"""
    assert (
        timedelta(hours=1),
        timedelta(hours=4),
        timedelta(hours=24),
        timedelta(hours=72),
    ) == MEASUREMENT_OFFSETS


def test_unplanned_measurement_point_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="не запланирован"):
        snapshot(timedelta(hours=2))


@pytest.mark.parametrize("field", ["views", "forwards", "reactions"])
def test_negative_counters_are_refused(field: str) -> None:
    with pytest.raises(InvalidValueError, match="меньше нуля"):
        snapshot(HOUR, **{field: -1})  # type: ignore[arg-type]


def test_watch_starts_empty_and_knows_what_comes_first() -> None:
    metrics = started()

    assert metrics.latest is None
    assert metrics.pending_offsets == MEASUREMENT_OFFSETS
    assert metrics.next_due_at == PUBLISHED_AT + HOUR
    assert not metrics.is_complete


def test_recording_moves_the_plan_forward() -> None:
    metrics = started()

    metrics.record(snapshot(HOUR))

    assert metrics.pending_offsets == (FOUR_HOURS, DAY, THREE_DAYS)
    assert metrics.next_due_at == PUBLISHED_AT + FOUR_HOURS
    assert metrics.latest is not None


def test_full_curve_completes_the_watch() -> None:
    metrics = started()

    for number, offset in enumerate(MEASUREMENT_OFFSETS, start=1):
        metrics.record(snapshot(offset, views=100 * number, forwards=number))

    assert metrics.is_complete
    assert metrics.next_due_at is None
    assert len(metrics.snapshots) == len(MEASUREMENT_OFFSETS)


def test_the_same_point_cannot_be_measured_twice() -> None:
    """Повторная доставка задачи не должна удваивать историю"""
    metrics = started()
    metrics.record(snapshot(HOUR))

    with pytest.raises(InvalidValueError, match="уже снят"):
        metrics.record(snapshot(HOUR))


def test_measurement_before_publication_is_refused() -> None:
    metrics = started()
    early = MetricsSnapshot(
        offset=HOUR,
        measured_at=PUBLISHED_AT - timedelta(minutes=1),
        views=1,
        forwards=0,
        reactions=0,
    )

    with pytest.raises(InvalidValueError, match="раньше публикации"):
        metrics.record(early)


@pytest.mark.parametrize("field", ["views", "forwards"])
def test_shrinking_counters_mean_a_broken_collector(field: str) -> None:
    """Telegram эти счётчики не уменьшает

    Падение означает не спад интереса, а сбор не с того сообщения. Такой замер
    лучше отвергнуть громко, чем потом строить по нему выводы.
    """
    metrics = started()
    metrics.record(snapshot(HOUR, views=500, forwards=20))

    with pytest.raises(InvalidValueError, match="не мог убыть"):
        metrics.record(snapshot(FOUR_HOURS, **{field: 1}))  # type: ignore[arg-type]


def test_reactions_may_go_down() -> None:
    """Реакции снимают, и это нормальная жизнь поста"""
    metrics = started()
    metrics.record(snapshot(HOUR, views=500, forwards=20, reactions=40))

    metrics.record(snapshot(FOUR_HOURS, views=600, forwards=25, reactions=31))

    assert metrics.latest is not None
    assert metrics.latest.reactions == 31


def test_delay_shows_how_late_the_worker_was() -> None:
    """Без этой величины непонятно, сравниваем мы час с часом или час с тремя"""
    metrics = started()
    late = snapshot(HOUR, late=timedelta(minutes=37))
    metrics.record(late)

    assert metrics.delay_of(late) == timedelta(minutes=37)


def test_watch_is_compared_by_the_post_it_belongs_to() -> None:
    metrics = started()
    same = PostMetrics.start(post_id=metrics.post_id, published_at=PUBLISHED_AT)

    assert metrics == same
    assert len({metrics, same}) == 1
    assert metrics != started()


def test_naive_publication_time_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="без часового пояса"):
        PostMetrics.start(post_id=PostId.new(), published_at=datetime(2026, 5, 1))  # noqa: DTZ001

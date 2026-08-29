"""Тесты жизненного цикла поста"""

from __future__ import annotations

from collections import deque

import pytest

from ai_blogger.domain.errors import IllegalTransitionError
from ai_blogger.domain.values.post_status import ALLOWED_TRANSITIONS, PostStatus

TERMINAL = {PostStatus.PUBLISHED, PostStatus.REJECTED}


def reachable_from(start: PostStatus, *, avoiding: PostStatus | None = None) -> set[PostStatus]:
    """Куда можно добраться из состояния, если обходить указанное стороной"""
    seen = {start}
    queue = deque([start])
    while queue:
        for target in ALLOWED_TRANSITIONS[queue.popleft()]:
            if target != avoiding and target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def test_every_status_is_described_in_the_table() -> None:
    """Новый статус обязан появиться в таблице переходов"""
    assert set(ALLOWED_TRANSITIONS) == set(PostStatus)


def test_table_points_only_at_known_statuses() -> None:
    reachable = {target for targets in ALLOWED_TRANSITIONS.values() for target in targets}

    assert reachable <= set(PostStatus)


def test_stored_values_stay_stable() -> None:
    """Значения уезжают в базу, поэтому переименование — это миграция"""
    assert {status.value for status in PostStatus} == {
        "draft",
        "needs_review",
        "approved",
        "published",
        "rejected",
        "generation_failed",
        "publication_failed",
    }


@pytest.mark.parametrize("status", list(PostStatus))
def test_only_published_and_rejected_are_final(status: PostStatus) -> None:
    assert status.is_final is (status in TERMINAL)


def test_every_status_is_reachable_from_a_draft() -> None:
    """Состояние, в которое нельзя попасть, — мёртвый код в таблице"""
    assert reachable_from(PostStatus.DRAFT) == set(PostStatus)


def test_manual_review_cannot_be_walked_around() -> None:
    """Инвариант, ради которого модуль и заведён — и который я едва не потерял

    Проверять отдельные переходы мало: пока провал был один на всех, из него
    вели два пути возврата, и вместе они складывались в обходную дорогу
    draft → провал → одобрено → опубликовано. Каждый переход по отдельности
    выглядел разумно, а сумма ломала гейт. Поэтому проверяем достижимость
    по графу, а не пары состояний.
    """
    without_review = reachable_from(PostStatus.DRAFT, avoiding=PostStatus.NEEDS_REVIEW)

    assert PostStatus.APPROVED not in without_review
    assert PostStatus.PUBLISHED not in without_review


def test_failures_return_to_where_they_happened() -> None:
    """Провал генерации и провал публикации возвращают в разные места"""
    assert ALLOWED_TRANSITIONS[PostStatus.GENERATION_FAILED] == frozenset({PostStatus.DRAFT})
    assert ALLOWED_TRANSITIONS[PostStatus.PUBLICATION_FAILED] == frozenset({PostStatus.APPROVED})


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PostStatus.DRAFT, PostStatus.NEEDS_REVIEW),
        (PostStatus.DRAFT, PostStatus.GENERATION_FAILED),
        (PostStatus.NEEDS_REVIEW, PostStatus.APPROVED),
        (PostStatus.NEEDS_REVIEW, PostStatus.REJECTED),
        (PostStatus.NEEDS_REVIEW, PostStatus.DRAFT),
        (PostStatus.APPROVED, PostStatus.PUBLISHED),
        (PostStatus.APPROVED, PostStatus.NEEDS_REVIEW),
        (PostStatus.APPROVED, PostStatus.PUBLICATION_FAILED),
        (PostStatus.GENERATION_FAILED, PostStatus.DRAFT),
        (PostStatus.PUBLICATION_FAILED, PostStatus.APPROVED),
    ],
)
def test_expected_transitions_are_allowed(source: PostStatus, target: PostStatus) -> None:
    """Полный проход конвейера из ТЗ, включая оба вида повторов"""
    source.ensure_can_move_to(target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PostStatus.DRAFT, PostStatus.PUBLISHED),
        (PostStatus.DRAFT, PostStatus.APPROVED),
        (PostStatus.NEEDS_REVIEW, PostStatus.PUBLISHED),
        (PostStatus.PUBLISHED, PostStatus.DRAFT),
        (PostStatus.REJECTED, PostStatus.APPROVED),
        (PostStatus.GENERATION_FAILED, PostStatus.APPROVED),
        (PostStatus.PUBLICATION_FAILED, PostStatus.DRAFT),
    ],
)
def test_shortcuts_past_review_are_forbidden(source: PostStatus, target: PostStatus) -> None:
    assert not source.can_move_to(target)
    with pytest.raises(IllegalTransitionError):
        source.ensure_can_move_to(target)


@pytest.mark.parametrize("status", list(PostStatus))
def test_moving_into_the_same_status_is_forbidden(status: PostStatus) -> None:
    """Повторная доставка задачи должна быть заметной, а не молча проходить"""
    with pytest.raises(IllegalTransitionError):
        status.ensure_can_move_to(status)


def test_error_names_both_statuses_and_the_way_out() -> None:
    with pytest.raises(IllegalTransitionError) as failure:
        PostStatus.PUBLISHED.ensure_can_move_to(PostStatus.DRAFT)

    message = str(failure.value)
    assert "published" in message
    assert "draft" in message
    assert "никуда" in message

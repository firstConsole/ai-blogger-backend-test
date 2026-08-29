"""Тесты жизненного цикла поста"""

from __future__ import annotations

from collections import deque

import pytest

from ai_blogger.domain.errors import IllegalTransitionError
from ai_blogger.domain.values.post_status import ALLOWED_TRANSITIONS, PostStatus

TERMINAL = {PostStatus.PUBLISHED, PostStatus.REJECTED}


def test_every_status_is_described_in_the_table() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(PostStatus)


def test_table_points_only_at_known_statuses() -> None:
    reachable = {target for targets in ALLOWED_TRANSITIONS.values() for target in targets}

    assert reachable <= set(PostStatus)


def test_stored_values_stay_stable() -> None:
    assert {status.value for status in PostStatus} == {
        "draft",
        "needs_review",
        "approved",
        "published",
        "rejected",
        "failed",
    }


@pytest.mark.parametrize("status", list(PostStatus))
def test_only_published_and_rejected_are_final(status: PostStatus) -> None:
    assert status.is_final is (status in TERMINAL)


def test_every_status_is_reachable_from_a_draft() -> None:
    """Состояние, в которое нельзя попасть, — мёртвый код в таблице"""
    seen = {PostStatus.DRAFT}
    queue = deque([PostStatus.DRAFT])
    while queue:
        for target in ALLOWED_TRANSITIONS[queue.popleft()]:
            if target not in seen:
                seen.add(target)
                queue.append(target)

    assert seen == set(PostStatus)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PostStatus.DRAFT, PostStatus.NEEDS_REVIEW),
        (PostStatus.NEEDS_REVIEW, PostStatus.APPROVED),
        (PostStatus.NEEDS_REVIEW, PostStatus.REJECTED),
        (PostStatus.NEEDS_REVIEW, PostStatus.DRAFT),
        (PostStatus.APPROVED, PostStatus.PUBLISHED),
        (PostStatus.APPROVED, PostStatus.NEEDS_REVIEW),
        (PostStatus.FAILED, PostStatus.DRAFT),
        (PostStatus.FAILED, PostStatus.APPROVED),
    ],
)
def test_expected_transitions_are_allowed(source: PostStatus, target: PostStatus) -> None:
    """Полный проход конвейера из ТЗ: черновик, ревью, одобрение, публикация"""
    source.ensure_can_move_to(target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PostStatus.DRAFT, PostStatus.PUBLISHED),
        (PostStatus.DRAFT, PostStatus.APPROVED),
        (PostStatus.NEEDS_REVIEW, PostStatus.PUBLISHED),
        (PostStatus.PUBLISHED, PostStatus.DRAFT),
        (PostStatus.REJECTED, PostStatus.APPROVED),
    ],
)
def test_shortcuts_past_review_are_forbidden(source: PostStatus, target: PostStatus) -> None:
    """Ручное подтверждение обойти нельзя — ради него гейт и заводился"""
    assert not source.can_move_to(target)
    with pytest.raises(IllegalTransitionError):
        source.ensure_can_move_to(target)


@pytest.mark.parametrize("status", list(PostStatus))
def test_moving_into_the_same_status_is_forbidden(status: PostStatus) -> None:
    """Повторная доставка задачи должна быть заметной, а не молча проходить"""
    with pytest.raises(IllegalTransitionError):
        status.ensure_can_move_to(status)


def test_error_names_both_statuses_and_the_way_out() -> None:
    """По тексту ошибки должно быть понятно, что делать, без чтения кода"""
    with pytest.raises(IllegalTransitionError) as failure:
        PostStatus.PUBLISHED.ensure_can_move_to(PostStatus.DRAFT)

    message = str(failure.value)
    assert "published" in message
    assert "draft" in message
    assert "никуда" in message

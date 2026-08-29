"""Тесты поста: подтверждение, публикация и повторы"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_blogger.domain.entities.post import MAX_REVIEW_NOTE_LENGTH, Post
from ai_blogger.domain.errors import IllegalTransitionError, InvalidValueError
from ai_blogger.domain.values.editorial import EditorialPolicy
from ai_blogger.domain.values.identifiers import ChannelId, TopicId
from ai_blogger.domain.values.language import Language
from ai_blogger.domain.values.post_status import PostStatus
from ai_blogger.domain.values.tags import Tag
from ai_blogger.domain.values.telegram import TelegramMessageId, TelegramUserId

EDITOR = TelegramUserId(123456789)
SLOT = datetime(2026, 5, 1, 18, 0, tzinfo=UTC)


def waiting_for_review() -> Post:
    post = Post.draft(
        channel_id=ChannelId.new(),
        topic_id=TopicId.new(),
        body="Нейросети научились считать. " * 15,
        tags=(Tag.parse("нейросети"),),
    )
    post.send_to_review()
    return post


def approved() -> Post:
    post = waiting_for_review()
    post.approve(publish_at=SLOT, reviewed_by=EDITOR)
    return post


def test_approval_records_who_said_yes_and_when_to_publish() -> None:
    """Без записи о том, кто одобрил, спорную публикацию разбирать не по чему"""
    post = approved()

    assert post.status is PostStatus.APPROVED
    assert post.publish_at == SLOT
    assert post.reviewed_by == EDITOR


def test_human_may_approve_a_post_that_failed_the_automatic_check() -> None:
    """Автоматическая проверка — подсказка человеку, а не запрет

    Если он видит текст и всё равно говорит «да», значит, у него есть
    причина, которой правила не знают.
    """
    strict = EditorialPolicy.of(
        language=Language("ru"),
        tone="спокойно",
        min_body_length=3000,
        max_body_length=4000,
        requires_image=True,
    )
    post = waiting_for_review()

    assert post.violations(strict)

    post.approve(publish_at=SLOT, reviewed_by=EDITOR)
    assert post.status is PostStatus.APPROVED


def test_rejection_keeps_the_reason() -> None:
    post = waiting_for_review()

    post.reject(note="  Слишком похоже на рекламу  ", reviewed_by=EDITOR)

    assert post.status is PostStatus.REJECTED
    assert post.review_note == "Слишком похоже на рекламу"
    assert post.reviewed_by == EDITOR


def test_rejection_is_final() -> None:
    post = waiting_for_review()
    post.reject(note="не то", reviewed_by=EDITOR)

    with pytest.raises(IllegalTransitionError):
        post.approve(publish_at=SLOT, reviewed_by=EDITOR)


def test_rework_returns_the_post_to_draft_with_a_note() -> None:
    """Тема хорошая, исполнение нет"""
    post = waiting_for_review()

    post.send_back_for_rework(note="Перепиши вступление", reviewed_by=EDITOR)

    assert post.status is PostStatus.DRAFT
    assert post.review_note == "Перепиши вступление"


@pytest.mark.parametrize("note", ["", "   "])
def test_decision_without_explanation_is_refused(note: str) -> None:
    with pytest.raises(InvalidValueError, match="ничего не объясняет"):
        waiting_for_review().reject(note=note, reviewed_by=EDITOR)


def test_overlong_note_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="комментарий длиннее"):
        waiting_for_review().reject(note="я" * (MAX_REVIEW_NOTE_LENGTH + 1), reviewed_by=EDITOR)


def test_naive_publication_time_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="без часового пояса"):
        waiting_for_review().approve(
            publish_at=datetime(2026, 5, 1, 18, 0),  # noqa: DTZ001
            reviewed_by=EDITOR,
        )


def test_approved_post_can_be_moved_to_another_slot() -> None:
    post = approved()

    post.reschedule(SLOT + timedelta(hours=2))

    assert post.publish_at == SLOT + timedelta(hours=2)


def test_only_an_approved_post_can_be_moved() -> None:
    with pytest.raises(IllegalTransitionError, match="только одобренный"):
        waiting_for_review().reschedule(SLOT)


def test_pulling_a_post_back_clears_its_slot() -> None:
    """Иначе снятый пост остался бы с назначенным временем и вышел бы сам"""
    post = approved()

    post.return_to_review()

    assert post.status is PostStatus.NEEDS_REVIEW
    assert post.publish_at is None


def test_publication_records_the_message_it_became() -> None:
    post = approved()

    post.mark_published(message_id=TelegramMessageId(4242), published_at=SLOT)

    assert post.status is PostStatus.PUBLISHED
    assert post.message_id == TelegramMessageId(4242)
    assert post.published_at == SLOT


def test_published_post_is_untouchable() -> None:
    post = approved()
    post.mark_published(message_id=TelegramMessageId(4242), published_at=SLOT)

    with pytest.raises(IllegalTransitionError):
        post.return_to_review()


def test_failed_publication_keeps_the_reason() -> None:
    post = approved()

    post.fail_publication("Telegram ответил 429")

    assert post.status is PostStatus.PUBLICATION_FAILED
    assert post.failure_reason == "Telegram ответил 429"


def test_retry_returns_the_post_to_the_queue() -> None:
    post = approved()
    post.fail_publication("Telegram ответил 429")

    post.retry_publication()

    assert post.status is PostStatus.APPROVED
    assert post.failure_reason is None
    assert post.publish_at == SLOT


def test_failed_publication_cannot_slip_back_into_a_draft() -> None:
    """Иначе провал публикации открыл бы дорогу в обход подтверждения"""
    post = approved()
    post.fail_publication("Telegram ответил 429")

    with pytest.raises(IllegalTransitionError):
        post.send_back_for_rework(note="переделать", reviewed_by=EDITOR)


def test_due_only_when_approved_and_the_time_has_come() -> None:
    post = approved()

    assert not post.is_due(SLOT - timedelta(seconds=1))
    assert post.is_due(SLOT)
    assert post.is_due(SLOT + timedelta(hours=1))


def test_a_post_awaiting_review_is_never_due() -> None:
    assert not waiting_for_review().is_due(SLOT)

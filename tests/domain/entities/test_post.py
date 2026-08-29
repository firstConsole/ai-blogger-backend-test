"""Тесты поста: путь от черновика до отправки на подтверждение"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from ai_blogger.domain.entities.post import (
    MAX_BODY_LENGTH,
    MAX_CRITIQUE_LENGTH,
    MAX_FAILURE_REASON_LENGTH,
    MAX_IMAGE_PROMPT_LENGTH,
    Post,
)
from ai_blogger.domain.errors import IllegalTransitionError, InvalidValueError
from ai_blogger.domain.values.editorial import CAPTION_LIMIT, MESSAGE_LIMIT, EditorialPolicy
from ai_blogger.domain.values.identifiers import ChannelId, MediaId, PostId, TopicId
from ai_blogger.domain.values.language import Language
from ai_blogger.domain.values.post_status import PostStatus
from ai_blogger.domain.values.tags import Tag
from ai_blogger.domain.values.telegram import TelegramMessageId, TelegramUserId

if TYPE_CHECKING:
    from collections.abc import Callable

CHANNEL = ChannelId.new()
TOPIC = TopicId.new()

BODY = "Нейросети научились считать. " * 15


def make_post(**overrides: object) -> Post:
    defaults: dict[str, object] = {
        "channel_id": CHANNEL,
        "topic_id": TOPIC,
        "body": BODY,
        "tags": (Tag.parse("нейросети"), Tag.parse("технологии")),
        "image_prompt": "минималистичная иллюстрация нейросети",
    }
    return Post.draft(**(defaults | overrides))  # type: ignore[arg-type]


def make_policy(**overrides: object) -> EditorialPolicy:
    defaults: dict[str, object] = {
        "language": Language("ru"),
        "tone": "спокойно",
        "min_body_length": 100,
        "max_body_length": 900,
        "min_tags": 2,
        "max_tags": 5,
        "requires_image": True,
    }
    return EditorialPolicy.of(**(defaults | overrides))  # type: ignore[arg-type]


def test_draft_starts_in_the_draft_status() -> None:
    post = make_post()

    assert isinstance(post.id, PostId)
    assert post.status is PostStatus.DRAFT
    assert post.image_id is None


def test_posts_are_compared_by_identity() -> None:
    post = make_post()
    same = make_post()
    same.id = post.id

    assert post == same
    assert len({post, same}) == 1
    assert make_post() != make_post()


def test_empty_body_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="публиковать нечего"):
        make_post(body="   ")


def test_repeated_tag_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="дважды"):
        make_post(tags=(Tag.parse("ai"), Tag.parse("AI")))


def test_overlong_image_prompt_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="промпт картинки"):
        make_post(image_prompt="а" * (MAX_IMAGE_PROMPT_LENGTH + 1))


def test_rewrite_replaces_text_and_tags() -> None:
    """Так выглядит повторная генерация после доработки"""
    post = make_post()

    post.rewrite("Совсем другой текст поста, достаточно длинный.", (Tag.parse("новости"),))

    assert post.body.startswith("Совсем другой")
    assert post.tags == (Tag.parse("новости"),)


def test_critique_is_kept_even_when_the_critic_is_happy() -> None:
    """Человеку важно видеть, что именно проверяли, а не только итог"""
    post = make_post()

    post.record_critique("  Стиль выдержан, фактических утверждений нет  ")

    assert post.critique == "Стиль выдержан, фактических утверждений нет"


@pytest.mark.parametrize("critique", ["", "   "])
def test_empty_critique_is_refused(critique: str) -> None:
    with pytest.raises(InvalidValueError, match="ничего не сообщает"):
        make_post().record_critique(critique)


def test_overlong_critique_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="вердикт критика длиннее"):
        make_post().record_critique("а" * (MAX_CRITIQUE_LENGTH + 1))


def test_draft_goes_to_review() -> None:
    post = make_post()

    post.send_to_review()

    assert post.status is PostStatus.NEEDS_REVIEW


def test_failed_generation_keeps_the_reason() -> None:
    post = make_post()

    post.fail_generation("  провайдер вернул 503  ")

    assert post.status is PostStatus.GENERATION_FAILED
    assert post.failure_reason == "провайдер вернул 503"


def test_retry_returns_the_post_to_draft_with_a_clean_slate() -> None:
    """Причина прошлого провала не должна остаться висеть на живом черновике"""
    post = make_post()
    post.fail_generation("провайдер вернул 503")

    post.retry_generation()

    assert post.status is PostStatus.DRAFT
    assert post.failure_reason is None


def test_long_failure_reason_is_trimmed_not_rejected() -> None:
    """Отказать из-за размера значило бы потерять объяснение целиком

    Сюда попадает текст исключения вместе с трассировкой стороннего клиента,
    и он бывает очень длинным именно тогда, когда нужен больше всего.
    """
    post = make_post()

    post.fail_generation("я" * (MAX_FAILURE_REASON_LENGTH * 3))

    assert post.failure_reason is not None
    assert len(post.failure_reason) == MAX_FAILURE_REASON_LENGTH
    assert post.failure_reason.endswith("…")


def test_empty_failure_reason_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="не поможет разобраться"):
        make_post().fail_generation("   ")


def test_review_cannot_be_requested_twice() -> None:
    """Повторная доставка задачи должна быть заметной"""
    post = make_post()
    post.send_to_review()

    with pytest.raises(IllegalTransitionError):
        post.send_to_review()


def test_a_fitting_post_has_no_complaints() -> None:
    post = make_post()
    post.attach_image(MediaId.new())

    assert post.violations(make_policy()) == ()
    assert post.fits(make_policy())


def test_violations_explain_themselves() -> None:
    """Этот список уходит человеку в админ-чат, а не только в лог"""
    post = make_post(body="Слишком коротко.", tags=())

    complaints = post.violations(make_policy())

    assert len(complaints) == 3
    assert any("длина" in complaint for complaint in complaints)
    assert any("тегов" in complaint for complaint in complaints)
    assert any("картинки нет" in complaint for complaint in complaints)


def test_channel_without_images_does_not_ask_for_one() -> None:
    """Проект настраивается под любой канал, в том числе текстовый"""
    post = make_post()

    assert post.fits(make_policy(requires_image=False))
    assert not post.fits(make_policy(requires_image=True))


def approved_post() -> Post:
    post = make_post()
    post.send_to_review()
    post.approve(publish_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC), reviewed_by=TelegramUserId(1))
    return post


@pytest.mark.parametrize(
    ("action", "call"),
    [
        ("правка текста", lambda post: post.rewrite("Другой текст поста. " * 10, ())),
        ("привязка картинки", lambda post: post.attach_image(MediaId.new())),
        ("вердикт критика", lambda post: post.record_critique("поздний вердикт")),
    ],
)
def test_content_cannot_be_changed_after_approval(
    action: str, call: Callable[[Post], None]
) -> None:
    """Иначе подтверждение перестаёт что-либо значить

    Человек одобряет один текст, а в канал уходит другой — и запись о том,
    кто одобрил, указывает на решение по прежнему тексту.
    """
    with pytest.raises(IllegalTransitionError, match=action):
        call(approved_post())


def test_published_post_is_frozen() -> None:
    """Строка в базе обязана совпадать с тем, что висит в Telegram"""
    post = approved_post()
    post.mark_published(
        message_id=TelegramMessageId(42), published_at=datetime(2026, 5, 1, 18, 0, tzinfo=UTC)
    )

    with pytest.raises(IllegalTransitionError):
        post.rewrite("подмена уже опубликованного", ())


def test_rework_reopens_the_post_for_editing() -> None:
    """Правка одобренного возможна, но только через возврат человеку"""
    post = approved_post()
    post.return_to_review()
    post.send_back_for_rework(note="перепиши", reviewed_by=TelegramUserId(1))

    post.rewrite("Переписанный текст поста. " * 10, (Tag.parse("новости"),))

    assert post.status is PostStatus.DRAFT


def test_zero_byte_from_a_feed_is_refused() -> None:
    """Postgres не хранит нулевой байт, и падение случилось бы уже в транзакции"""
    with pytest.raises(InvalidValueError, match="нулевой байт"):
        make_post(body="Текст поста\x00с мусором из битой кодировки. " * 5)


def test_control_characters_are_refused() -> None:
    with pytest.raises(InvalidValueError, match="управляющий символ"):
        make_post(body="Текст поста\x07со звонком терминала. " * 5)


def test_body_longer_than_telegram_allows_is_refused() -> None:
    """Ответ модели любого размера не должен уезжать в базу"""
    with pytest.raises(InvalidValueError, match="не примет сообщение"):
        make_post(body="я" * (MAX_BODY_LENGTH + 1))


def test_post_too_long_for_a_caption_is_flagged() -> None:
    """Такой пост Telegram не примет одним сообщением с картинкой"""
    post = make_post(body="я" * (CAPTION_LIMIT + 1))
    post.attach_image(MediaId.new())

    complaints = post.violations(make_policy(min_body_length=100, max_body_length=MESSAGE_LIMIT))

    assert any("подпись к фото" in complaint for complaint in complaints)

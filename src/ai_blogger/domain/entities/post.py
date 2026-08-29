"""Пост канала"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.identifiers import PostId
from ai_blogger.domain.values.post_status import PostStatus

if TYPE_CHECKING:
    from ai_blogger.domain.values.editorial import EditorialPolicy
    from ai_blogger.domain.values.identifiers import ChannelId, MediaId, TopicId
    from ai_blogger.domain.values.tags import Tag

MAX_IMAGE_PROMPT_LENGTH = 1000
MAX_CRITIQUE_LENGTH = 4000
MAX_FAILURE_REASON_LENGTH = 500


@dataclass(eq=False, slots=True)
class Post:
    id: PostId
    channel_id: ChannelId
    topic_id: TopicId
    status: PostStatus
    body: str
    tags: tuple[Tag, ...] = ()
    image_prompt: str | None = None
    image_id: MediaId | None = None
    critique: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _check_body(self.body)
        if len(set(self.tags)) != len(self.tags):
            raise InvalidValueError("один и тот же тег добавлен дважды")
        if self.image_prompt is not None:
            _check_image_prompt(self.image_prompt)

    @classmethod
    def draft(
        cls,
        *,
        channel_id: ChannelId,
        topic_id: TopicId,
        body: str,
        tags: tuple[Tag, ...] = (),
        image_prompt: str | None = None,
    ) -> Self:
        """Записать то, что вернула модель черновика"""
        return cls(
            id=PostId.new(),
            channel_id=channel_id,
            topic_id=topic_id,
            status=PostStatus.DRAFT,
            body=body.strip(),
            tags=tags,
            image_prompt=image_prompt.strip() if image_prompt else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Post):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def rewrite(self, body: str, tags: tuple[Tag, ...] = ()) -> None:
        """Заменить текст: так выглядит повторная генерация после доработки"""
        stripped = body.strip()
        _check_body(stripped)
        if len(set(tags)) != len(tags):
            raise InvalidValueError("один и тот же тег добавлен дважды")
        self.body = stripped
        self.tags = tags

    def attach_image(self, image_id: MediaId) -> None:
        """Привязать сгенерированную картинку"""
        self.image_id = image_id

    def record_critique(self, critique: str) -> None:
        """Сохранить вердикт критика

        Хранится даже когда критик всем доволен: человеку в админ-чате важно
        видеть, что именно проверяли, а не только итог.
        """
        stripped = critique.strip()
        if not stripped:
            raise InvalidValueError("пустой вердикт критика ничего не сообщает")
        if len(stripped) > MAX_CRITIQUE_LENGTH:
            raise InvalidValueError(f"вердикт критика длиннее {MAX_CRITIQUE_LENGTH} символов")
        self.critique = stripped

    def send_to_review(self) -> None:
        """Отправить человеку на подтверждение"""
        self.status.ensure_can_move_to(PostStatus.NEEDS_REVIEW)
        self.status = PostStatus.NEEDS_REVIEW

    def fail_generation(self, reason: str) -> None:
        """Признать, что собрать пост не вышло"""
        self.status.ensure_can_move_to(PostStatus.GENERATION_FAILED)
        self.failure_reason = _reason(reason)
        self.status = PostStatus.GENERATION_FAILED

    def retry_generation(self) -> None:
        """Вернуть в работу после неудачной генерации"""
        self.status.ensure_can_move_to(PostStatus.DRAFT)
        self.failure_reason = None
        self.status = PostStatus.DRAFT

    def violations(self, policy: EditorialPolicy) -> tuple[str, ...]:
        """Чем пост не подходит каналу

        Возвращает список причин, а не «да/нет»: этот же список уходит
        человеку в админ-чат, и «пост не годится» без объяснения заставило
        бы его сверять правила руками.
        """
        found: list[str] = []
        if not policy.accepts_body_length(len(self.body)):
            found.append(
                f"длина {len(self.body)} вне разрешённых "
                f"{policy.min_body_length}–{policy.max_body_length}"
            )
        if not policy.accepts_tag_count(len(self.tags)):
            found.append(
                f"тегов {len(self.tags)}, а нужно от {policy.min_tags} до {policy.max_tags}"
            )
        if policy.requires_image and self.image_id is None:
            found.append("канал выходит с картинками, а картинки нет")
        return tuple(found)

    def fits(self, policy: EditorialPolicy) -> bool:
        """Готов ли пост к тому, чтобы показать его человеку"""
        return not self.violations(policy)


def _check_body(body: str) -> None:
    if not body:
        raise InvalidValueError("пустой пост публиковать нечего")
    if body != body.strip():
        raise InvalidValueError("в тексте поста лишние пробелы по краям")


def _reason(reason: str) -> str:
    """Привести причину провала к пригодному для хранения виду"""
    stripped = reason.strip()

    if not stripped:
        raise InvalidValueError("причина провала без текста не поможет разобраться")
    if len(stripped) <= MAX_FAILURE_REASON_LENGTH:
        return stripped
    return stripped[: MAX_FAILURE_REASON_LENGTH - 1] + "…"


def _check_image_prompt(prompt: str) -> None:
    if not prompt.strip():
        raise InvalidValueError("пустой промпт картинки ничего не нарисует")
    if len(prompt) > MAX_IMAGE_PROMPT_LENGTH:
        raise InvalidValueError(f"промпт картинки длиннее {MAX_IMAGE_PROMPT_LENGTH} символов")

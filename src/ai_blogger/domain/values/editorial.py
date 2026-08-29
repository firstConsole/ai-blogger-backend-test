"""Редполитика канала"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ai_blogger.domain.values.language import Language

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
MAX_TONE_LENGTH = 500
MAX_TAGS = 10
MAX_BANNED_TOPICS = 100


@dataclass(frozen=True, slots=True)
class EditorialPolicy:
    language: Language
    tone: str
    min_body_length: int
    max_body_length: int
    min_tags: int
    max_tags: int
    banned_topics: frozenset[str]
    requires_image: bool

    def __post_init__(self) -> None:
        self._check_tone()
        self._check_body_length()
        self._check_tags()
        self._check_banned_topics()

    def _check_tone(self) -> None:
        if not self.tone.strip():
            raise InvalidValueError("тон канала не может быть пустым")

        if self.tone != self.tone.strip():
            raise InvalidValueError("тон канала не должен начинаться или кончаться пробелами")

        if len(self.tone) > MAX_TONE_LENGTH:
            raise InvalidValueError(
                f"описание тона длиннее {MAX_TONE_LENGTH} символов: оно уедет в каждый "
                "промпт, и место там дорогое"
            )

    def _check_body_length(self) -> None:
        if self.min_body_length < 1:
            raise InvalidValueError("минимальная длина поста должна быть положительной")

        if self.min_body_length > self.max_body_length:
            raise InvalidValueError(
                f"минимальная длина {self.min_body_length} больше максимальной "
                f"{self.max_body_length}"
            )

        if self.max_body_length > MESSAGE_LIMIT:
            raise InvalidValueError(
                f"Telegram не примет сообщение длиннее {MESSAGE_LIMIT} символов, "
                f"а политика разрешает {self.max_body_length}"
            )

    def _check_tags(self) -> None:
        if self.min_tags < 0:
            raise InvalidValueError("количество тегов не может быть отрицательным")

        if self.min_tags > self.max_tags:
            raise InvalidValueError(
                f"минимум тегов {self.min_tags} больше максимума {self.max_tags}"
            )

        if self.max_tags > MAX_TAGS:
            raise InvalidValueError(f"больше {MAX_TAGS} тегов читается как спам, а не как метки")

    def _check_banned_topics(self) -> None:
        if len(self.banned_topics) > MAX_BANNED_TOPICS:
            raise InvalidValueError(f"запретов больше {MAX_BANNED_TOPICS} — их никто не соблюдёт")
        for topic in self.banned_topics:
            if not topic:
                raise InvalidValueError("пустой запрет ничего не запрещает")

            if topic != topic.strip().lower():
                raise InvalidValueError(
                    f"запрет должен быть нормализован, соберите через of: «{topic}»"
                )

    @classmethod
    def of(
        cls,
        *,
        language: Language,
        tone: str,
        min_body_length: int,
        max_body_length: int,
        min_tags: int = 0,
        max_tags: int = MAX_TAGS,
        banned_topics: Iterable[str] = (),
        requires_image: bool = True,
    ) -> Self:
        normalized = frozenset(
            stripped for topic in banned_topics if (stripped := topic.strip().lower())
        )

        return cls(
            language=language,
            tone=tone.strip(),
            min_body_length=min_body_length,
            max_body_length=max_body_length,
            min_tags=min_tags,
            max_tags=max_tags,
            banned_topics=normalized,
            requires_image=requires_image,
        )

    @property
    def fits_single_telegram_message(self) -> bool:
        limit = CAPTION_LIMIT if self.requires_image else MESSAGE_LIMIT
        return self.max_body_length <= limit

    def accepts_body_length(self, length: int) -> bool:
        """Проходит ли текст такой длины по правилам канала"""
        return self.min_body_length <= length <= self.max_body_length

    def accepts_tag_count(self, count: int) -> bool:
        """Проходит ли такое количество тегов"""
        return self.min_tags <= count <= self.max_tags

"""Порты генерации контента"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_blogger.domain.entities.post import Post
    from ai_blogger.domain.entities.topic import Topic
    from ai_blogger.domain.values.editorial import EditorialPolicy
    from ai_blogger.domain.values.embeddings import Embedding


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Во что обошёлся вызов модели"""

    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class WrittenDraft:
    """Что вернула модель черновика"""

    body: str
    image_prompt: str
    tags: tuple[str, ...]
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class Critique:
    """Вердикт критика"""

    approved: bool
    notes: str
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class DrawnImage:
    """Готовая картинка до того, как она попала в хранилище"""

    content: bytes
    content_type: str


class DraftWriter(Protocol):
    """Модель, которая пишет пост"""

    async def write(
        self, *, topic: Topic, policy: EditorialPolicy, hints: Sequence[str] = ()
    ) -> WrittenDraft:
        """Написать черновик по теме"""
        ...


class Critic(Protocol):
    """Модель, которая проверяет пост перед показом человеку"""

    async def review(self, *, post: Post, policy: EditorialPolicy) -> Critique:
        """Проверить согласованность, стиль и соответствие редполитике"""
        ...


class ImageArtist(Protocol):
    """Модель, которая рисует иллюстрацию"""

    async def draw(self, prompt: str) -> DrawnImage:
        """Нарисовать картинку по промпту из черновика"""
        ...


class TextEncoder(Protocol):
    """Модель, считающая эмбеддинги заголовков"""

    async def encode(self, text: str) -> Embedding:
        """Посчитать вектор заголовка"""
        ...

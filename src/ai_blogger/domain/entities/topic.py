"""Тема, найденная для канала"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.embeddings import DEDUPLICATION_WINDOW, DUPLICATE_THRESHOLD
from ai_blogger.domain.values.identifiers import TopicId
from ai_blogger.domain.values.sources import TopicOrigin
from ai_blogger.domain.values.text import ensure_storable

if TYPE_CHECKING:
    from datetime import datetime

    from ai_blogger.domain.values.embeddings import Embedding
    from ai_blogger.domain.values.identifiers import ChannelId
    from ai_blogger.domain.values.sources import SourceUrl

MAX_TITLE_LENGTH = 300

ORIGINS_REQUIRING_A_LINK = frozenset({TopicOrigin.FEED, TopicOrigin.SEARCH})


@dataclass(eq=False, slots=True)
class Topic:
    """Информационный повод, из которого может вырасти пост"""

    id: TopicId
    channel_id: ChannelId
    title: str
    origin: TopicOrigin
    discovered_at: datetime
    embedding: Embedding
    url: SourceUrl | None = None
    discovered_from: str | None = None
    """Адрес ленты или текст запроса, из которого пришла тема.

    Без этого поля непонятно, какой источник приносит темы, которые доходят до
    публикации, а какой — шум. Недельная выжимка из ТЗ считает топ тем; чтобы
    из неё следовало действие, нужно знать, откуда эти темы взялись.
    """

    def __post_init__(self) -> None:
        _check_title(self.title)
        if self.discovered_at.tzinfo is None:
            raise InvalidValueError("время обнаружения без часового пояса ни с чем не сравнить")
        if self.origin in ORIGINS_REQUIRING_A_LINK and self.url is None:
            raise InvalidValueError(
                f"тема из источника «{self.origin}» обязана ссылаться на первоисточник"
            )

    @classmethod
    def discover(
        cls,
        *,
        channel_id: ChannelId,
        title: str,
        origin: TopicOrigin,
        discovered_at: datetime,
        embedding: Embedding,
        url: SourceUrl | None = None,
        discovered_from: str | None = None,
    ) -> Self:
        """Записать найденную тему"""
        return cls(
            id=TopicId.new(),
            channel_id=channel_id,
            title=" ".join(title.split()),
            origin=origin,
            discovered_at=discovered_at,
            embedding=embedding,
            url=url,
            discovered_from=discovered_from,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Topic):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def is_duplicate_of(self, other: Topic, threshold: float = DUPLICATE_THRESHOLD) -> bool:
        if self.channel_id != other.channel_id:
            return False
        if abs(self.discovered_at - other.discovered_at) > DEDUPLICATION_WINDOW:
            return False
        return self.embedding.is_duplicate_of(other.embedding, threshold)


def _check_title(title: str) -> None:
    if not title:
        raise InvalidValueError("у темы должен быть заголовок")
    if title != " ".join(title.split()):
        raise InvalidValueError("в заголовке лишние пробелы, используйте discover")

    ensure_storable(title, "заголовок темы")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidValueError(
            f"заголовок длиннее {MAX_TITLE_LENGTH} символов — это уже не заголовок, "
            f"получено {len(title)}"
        )

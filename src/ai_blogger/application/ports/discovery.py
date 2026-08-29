"""Порты поиска тем"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from ai_blogger.domain.values.sources import SearchQuery, SourceUrl


@dataclass(frozen=True, slots=True)
class FoundTopic:
    """Заголовок, найденный в источнике"""

    title: str
    url: SourceUrl
    published_at: datetime | None


class FeedReader(Protocol):
    """Читатель RSS-лент"""

    async def read(self, feed: SourceUrl) -> Sequence[FoundTopic]:
        """Вычитать свежие записи ленты"""
        ...


class WebSearch(Protocol):
    """Поиск по вебу"""

    async def search(self, query: SearchQuery) -> Sequence[FoundTopic]:
        """Найти свежие материалы по запросу"""
        ...

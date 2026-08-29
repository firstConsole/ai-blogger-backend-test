"""Идентификаторы сущностей"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from ai_blogger.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class EntityId:
    """Идентификатор сущности"""

    value: UUID

    @classmethod
    def new(cls) -> Self:
        """Выдать новый идентификатор"""
        return cls(uuid4())

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Разобрать идентификатор из строки"""
        try:
            return cls(UUID(raw))
        except ValueError as error:
            raise InvalidValueError(
                f"{cls.__name__}: «{raw}» не похоже на идентификатор"
            ) from error

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ChannelId(EntityId):
    """Канал, который ведёт блогер"""


@dataclass(frozen=True, slots=True)
class TopicId(EntityId):
    """Тема, найденная в источниках"""


@dataclass(frozen=True, slots=True)
class PostId(EntityId):
    """Пост на любой стадии"""


@dataclass(frozen=True, slots=True)
class MediaId(EntityId):
    """Картинка в объектном хранилище"""

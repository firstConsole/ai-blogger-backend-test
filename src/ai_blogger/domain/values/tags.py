"""Теги поста"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Self

from ai_blogger.domain.errors import InvalidValueError

MAX_TAG_LENGTH = 64


def _is_allowed(character: str) -> bool:
    return character.isalpha() or character.isdecimal() or character == "_"


@dataclass(frozen=True, slots=True)
class Tag:
    """Тег поста в каноническом виде"""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidValueError("тег не может быть пустым")

        if unicodedata.normalize("NFC", self.value) != self.value:
            raise InvalidValueError(
                f"тег должен быть в нормальной форме NFC, используйте parse: «{self.value}»"
            )

        if len(self.value) > MAX_TAG_LENGTH:
            raise InvalidValueError(f"тег длиннее {MAX_TAG_LENGTH} символов: «{self.value}»")

        if not all(_is_allowed(character) for character in self.value):
            raise InvalidValueError(
                f"в теге допустимы только буквы, цифры и подчёркивание: «{self.value}»"
            )

        if not any(character.isalpha() for character in self.value):
            raise InvalidValueError(f"тег без единой буквы ничего не помечает: «{self.value}»")

        if self.value != self.value.lower():
            raise InvalidValueError(
                f"тег должен быть в нижнем регистре, используйте parse: «{self.value}»"
            )

    @classmethod
    def parse(cls, raw: str) -> Self:
        normalized = unicodedata.normalize("NFC", raw)
        return cls(normalized.strip().lstrip("#").strip().lower())

    def __str__(self) -> str:
        return f"#{self.value}"

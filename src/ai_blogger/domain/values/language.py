"""Язык канала"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from ai_blogger.domain.errors import InvalidValueError

MIN_CODE_LENGTH = 2
MAX_CODE_LENGTH = 3


@dataclass(frozen=True, slots=True)
class Language:
    """Язык, на котором канал разговаривает с читателем
    Код ISO 639 в нижнем регистре: ru, en, kk. Это настройка канала, а не
    константа проекта — блогер должен одинаково вести канал на любом языке.
    """

    code: str

    def __post_init__(self) -> None:
        length = len(self.code)
        if not (MIN_CODE_LENGTH <= length <= MAX_CODE_LENGTH):
            raise InvalidValueError(
                f"код языка ISO 639 состоит из 2-3 букв, получено «{self.code}»"
            )
        if not self.code.isascii() or not self.code.isalpha() or not self.code.islower():
            raise InvalidValueError(
                f"код языка — латиница в нижнем регистре, получено «{self.code}»"
            )

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Разобрать код языка, не придираясь к регистру и пробелам"""
        return cls(raw.strip().lower())

    def __str__(self) -> str:
        return self.code

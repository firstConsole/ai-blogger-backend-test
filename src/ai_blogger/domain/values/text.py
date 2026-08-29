"""Проверка текста, пришедшего снаружи"""

from __future__ import annotations

import unicodedata

from ai_blogger.domain.errors import InvalidValueError

ALLOWED_CONTROLS = frozenset({"\n", "\r", "\t"})


def ensure_storable(value: str, what: str) -> None:
    """Отказать в тексте, который не доедет до базы или приедет не тем, чем был отправлен"""
    if "\x00" in value:
        raise InvalidValueError(f"{what}: нулевой байт — такой текст не сохранит база")

    for character in value:
        if unicodedata.category(character) == "Cc" and character not in ALLOWED_CONTROLS:
            raise InvalidValueError(
                f"{what}: управляющий символ U+{ord(character):04X} в тексте не место"
            )

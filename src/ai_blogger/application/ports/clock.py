"""Часы"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """Источник текущего времени"""

    def now(self) -> datetime:
        """Текущий момент, обязательно с часовым поясом"""
        ...

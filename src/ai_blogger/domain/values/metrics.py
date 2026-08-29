"""Замеры показателей поста"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from datetime import datetime

MEASUREMENT_OFFSETS: Final = (
    timedelta(hours=1),
    timedelta(hours=4),
    timedelta(hours=24),
    timedelta(hours=72),
)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Показатели поста, снятые в одну из запланированных точек"""

    offset: timedelta
    measured_at: datetime
    views: int
    forwards: int
    reactions: int

    def __post_init__(self) -> None:
        if self.offset not in MEASUREMENT_OFFSETS:
            raise InvalidValueError(
                f"замер через {self.offset} не запланирован; "
                f"точки: {', '.join(str(offset) for offset in MEASUREMENT_OFFSETS)}"
            )
        if self.measured_at.tzinfo is None:
            raise InvalidValueError("время замера без часового пояса ни с чем не сравнить")
        for name, value in (
            ("просмотров", self.views),
            ("пересылок", self.forwards),
            ("реакций", self.reactions),
        ):
            if value < 0:
                raise InvalidValueError(f"{name} не может быть меньше нуля, получено {value}")

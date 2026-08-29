"""Расписание публикаций канала"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable

SEARCH_HORIZON_DAYS = 10


@dataclass(frozen=True, slots=True)
class PublicationSchedule:
    timezone: ZoneInfo
    slots: tuple[time, ...]

    def __post_init__(self) -> None:
        if not self.slots:
            raise InvalidValueError("в расписании должен быть хотя бы один слот")
        if any(slot.tzinfo is not None for slot in self.slots):
            raise InvalidValueError("слот — это время суток, часовой пояс задаётся отдельно")
        if len(set(self.slots)) != len(self.slots):
            raise InvalidValueError("слоты расписания не должны повторяться")
        if tuple(sorted(self.slots)) != self.slots:
            raise InvalidValueError("слоты должны идти по возрастанию, соберите через of")

    @classmethod
    def of(cls, timezone: str, slots: Iterable[time]) -> Self:
        """Собрать расписание из настроек канала, приведя слоты в порядок"""
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise InvalidValueError(f"неизвестный часовой пояс «{timezone}»") from error
        return cls(zone, tuple(sorted(set(slots))))

    @property
    def posts_per_day(self) -> int:
        """Сколько постов канал выпускает в сутки"""
        return len(self.slots)

    def wall_clock_exists(self, reading: datetime) -> bool:
        if reading.tzinfo is not None:
            raise InvalidValueError("показание часов задаётся без часового пояса")

        attached = reading.replace(tzinfo=self.timezone)
        restored = attached.astimezone(UTC).astimezone(self.timezone)
        return restored.replace(tzinfo=None) == reading

    def next_slot_after(self, moment: datetime) -> datetime:
        """Ближайшее время публикации после указанного момента, в часовом поясе канала"""
        if moment.tzinfo is None:
            raise InvalidValueError("момент без часового пояса сравнивать не с чем")

        instant = moment.astimezone(UTC)
        first_day = moment.astimezone(self.timezone).date()

        for offset in range(SEARCH_HORIZON_DAYS):
            day = first_day + timedelta(days=offset)
            for slot in self.slots:
                reading = datetime.combine(day, slot)
                if not self.wall_clock_exists(reading):
                    continue
                candidate = reading.replace(tzinfo=self.timezone)
                if candidate.astimezone(UTC) > instant:
                    return candidate

        raise InvalidValueError(
            f"за {SEARCH_HORIZON_DAYS} суток в поясе «{self.timezone.key}» не нашлось "
            "ни одного существующего слота"
        )

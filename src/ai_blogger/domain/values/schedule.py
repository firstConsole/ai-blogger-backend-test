"""Расписание публикаций канала"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import IntEnum
from typing import TYPE_CHECKING, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

DAYS_IN_WEEK = 7
SEARCH_HORIZON_DAYS = 21


class Weekday(IntEnum):
    """День недели. Значения совпадают с date.weekday(): понедельник — ноль"""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass(frozen=True, slots=True)
class PublicationSchedule:
    timezone: ZoneInfo
    slots_by_weekday: tuple[tuple[time, ...], ...]

    def __post_init__(self) -> None:
        if len(self.slots_by_weekday) != DAYS_IN_WEEK:
            raise InvalidValueError(
                f"в неделе {DAYS_IN_WEEK} дней, а в расписании {len(self.slots_by_weekday)}"
            )
        if not any(self.slots_by_weekday):
            raise InvalidValueError(
                "расписание без единого слота — это канал, который молчит всегда"
            )
        for weekday, slots in zip(Weekday, self.slots_by_weekday, strict=True):
            _check_day(weekday, slots)

    @classmethod
    def of(cls, timezone: str, slots: Iterable[time]) -> Self:
        """Одни и те же слоты каждый день"""
        ordered = _order(slots)
        return cls(_zone(timezone), tuple(ordered for _ in Weekday))

    @classmethod
    def by_weekday(cls, timezone: str, slots: Mapping[Weekday, Iterable[time]]) -> Self:
        """Свои слоты для каждого дня недели

        Дни, которых нет в переданном отображении, канал молчит.
        """
        return cls(
            _zone(timezone),
            tuple(_order(slots.get(weekday, ())) for weekday in Weekday),
        )

    def slots_on(self, weekday: Weekday) -> tuple[time, ...]:
        """Слоты конкретного дня недели"""
        return self.slots_by_weekday[weekday]

    def is_silent_on(self, weekday: Weekday) -> bool:
        """Молчит ли канал в этот день"""
        return not self.slots_on(weekday)

    @property
    def posts_per_week(self) -> int:
        """Сколько постов канал выпускает за неделю"""
        return sum(len(slots) for slots in self.slots_by_weekday)

    def wall_clock_exists(self, reading: datetime) -> bool:
        if reading.tzinfo is not None:
            raise InvalidValueError("показание часов задаётся без часового пояса")

        attached = reading.replace(tzinfo=self.timezone)
        restored = attached.astimezone(UTC).astimezone(self.timezone)

        return restored.replace(tzinfo=None) == reading

    def next_slot_after(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            raise InvalidValueError("момент без часового пояса сравнивать не с чем")

        instant = moment.astimezone(UTC)
        first_day = moment.astimezone(self.timezone).date()

        for offset in range(SEARCH_HORIZON_DAYS):
            day = first_day + timedelta(days=offset)
            for slot in self.slots_on(Weekday(day.weekday())):
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


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidValueError(f"неизвестный часовой пояс «{timezone}»") from error


def _order(slots: Iterable[time]) -> tuple[time, ...]:
    return tuple(sorted(set(slots)))


def _check_day(weekday: Weekday, slots: tuple[time, ...]) -> None:
    if any(slot.tzinfo is not None for slot in slots):
        raise InvalidValueError(
            f"{weekday.name}: слот — это время суток, часовой пояс задаётся отдельно"
        )
    if len(set(slots)) != len(slots):
        raise InvalidValueError(f"{weekday.name}: слоты расписания не должны повторяться")
    if tuple(sorted(slots)) != slots:
        raise InvalidValueError(
            f"{weekday.name}: слоты должны идти по возрастанию, соберите через of"
        )

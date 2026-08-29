"""Расписание публикаций канала"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable


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

    def exists_on_the_wall_clock(self, moment: datetime) -> bool:
        restored = moment.astimezone(UTC).astimezone(self.timezone)
        return restored.replace(tzinfo=None) == moment.replace(tzinfo=None)

    def next_slot_after(self, moment: datetime) -> datetime:
        if moment.tzinfo is None:
            raise InvalidValueError("момент без часового пояса сравнивать не с чем")

        local = moment.astimezone(self.timezone)
        today = local.date()

        for day in (today, today + timedelta(days=1)):
            for slot in self.slots:
                candidate = datetime.combine(day, slot, tzinfo=self.timezone)

                if candidate > local and self.exists_on_the_wall_clock(candidate):
                    return candidate

        raise InvalidValueError(
            "за двое суток не нашлось ни одного слота — часовой пояс "
            f"«{self.timezone.key}» переставлял часы больше чем на день"
        )

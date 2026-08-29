"""Тесты расписания публикаций"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.schedule import PublicationSchedule

BERLIN = ZoneInfo("Europe/Berlin")
SPRING_FORWARD = datetime(2026, 3, 29, tzinfo=BERLIN).date()
FALL_BACK = datetime(2026, 10, 25, tzinfo=BERLIN).date()


def test_of_sorts_slots_and_drops_duplicates() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(18, 0), time(9, 0), time(9, 0)])

    assert schedule.slots == (time(9, 0), time(18, 0))
    assert schedule.posts_per_day == 2


def test_constructor_refuses_unsorted_slots() -> None:
    with pytest.raises(InvalidValueError, match="по возрастанию"):
        PublicationSchedule(BERLIN, (time(18, 0), time(9, 0)))


def test_schedule_without_slots_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="хотя бы один слот"):
        PublicationSchedule.of("Europe/Berlin", [])


def test_slot_carrying_its_own_timezone_is_rejected() -> None:
    """Часовой пояс у расписания один, иначе непонятно, кто главнее"""
    with pytest.raises(InvalidValueError, match="время суток"):
        PublicationSchedule(BERLIN, (time(9, 0, tzinfo=UTC),))


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="часовой пояс"):
        PublicationSchedule.of("Europe/Middle_Earth", [time(9, 0)])


def test_next_slot_is_found_within_the_same_day() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(9, 0), time(18, 0)])
    following = schedule.next_slot_after(datetime(2026, 5, 1, 10, 0, tzinfo=BERLIN))

    assert following == datetime(2026, 5, 1, 18, 0, tzinfo=BERLIN)


def test_after_the_last_slot_the_next_one_is_tomorrow() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(9, 0), time(18, 0)])
    following = schedule.next_slot_after(datetime(2026, 5, 1, 23, 0, tzinfo=BERLIN))

    assert following == datetime(2026, 5, 2, 9, 0, tzinfo=BERLIN)


def test_moment_in_another_timezone_is_converted_first() -> None:
    """Планировщик живёт в UTC, канал — в своём поясе"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(9, 0)])

    following = schedule.next_slot_after(datetime(2026, 5, 1, 6, 0, tzinfo=UTC))

    assert following == datetime(2026, 5, 1, 9, 0, tzinfo=BERLIN)


def test_naive_moment_is_rejected() -> None:
    """Наивное время сравнивать не с чем — ruff запрещает такие даты не зря"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(9, 0)])

    with pytest.raises(InvalidValueError, match="без часового пояса"):
        schedule.next_slot_after(datetime(2026, 5, 1, 10, 0))  # noqa: DTZ001


def test_slot_inside_the_lost_hour_does_not_exist() -> None:
    """Весной часы прыгают с 02:00 на 03:00 — времени 02:30 в этот день нет"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])
    lost = datetime.combine(SPRING_FORWARD, time(2, 30), tzinfo=BERLIN)

    assert not schedule.exists_on_the_wall_clock(lost)
    assert schedule.exists_on_the_wall_clock(lost + timedelta(days=1))


def test_two_slots_never_collapse_into_one_moment_on_the_transition_day() -> None:
    """Ради этого случая проверка на существование и заводилась

    Без неё слоты 02:30 и 03:30 указывали бы на одну и ту же секунду UTC,
    и канал раз в год выпускал бы два поста одновременно.
    """
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30), time(3, 30)])

    first = schedule.next_slot_after(datetime.combine(SPRING_FORWARD, time(0, 30), tzinfo=BERLIN))
    second = schedule.next_slot_after(first)

    assert first == datetime.combine(SPRING_FORWARD, time(3, 30), tzinfo=BERLIN)
    assert second.date() > SPRING_FORWARD
    assert first.astimezone(UTC) != second.astimezone(UTC)


def test_only_slot_lost_to_the_transition_moves_to_the_next_day() -> None:
    """Канал выпустит в этот день на пост меньше — это честнее, чем сдвиг"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])

    following = schedule.next_slot_after(
        datetime.combine(SPRING_FORWARD, time(0, 0), tzinfo=BERLIN)
    )

    assert following.date() == SPRING_FORWARD + timedelta(days=1)


def test_repeated_hour_in_autumn_gives_one_publication_not_two() -> None:
    """Осенью 02:30 наступает дважды, но пост выходит один раз"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])

    first = schedule.next_slot_after(datetime.combine(FALL_BACK, time(0, 0), tzinfo=BERLIN))
    second = schedule.next_slot_after(first)

    assert first.date() == FALL_BACK
    assert first.fold == 0
    assert second.date() == FALL_BACK + timedelta(days=1)


def test_a_whole_year_of_slots_never_repeats_a_moment() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30), time(3, 30), time(14, 0)])

    moment = datetime(2026, 1, 1, tzinfo=BERLIN)
    seen: list[datetime] = []

    while moment.year == 2026:
        moment = schedule.next_slot_after(moment)
        seen.append(moment)

    instants = [point.astimezone(UTC) for point in seen]
    assert instants == sorted(instants)
    assert len(set(instants)) == len(instants)

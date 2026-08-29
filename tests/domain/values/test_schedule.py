"""Тесты расписания публикаций"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.schedule import PublicationSchedule, Weekday

BERLIN = ZoneInfo("Europe/Berlin")

SPRING_FORWARD = datetime(2026, 3, 29, tzinfo=BERLIN).date()
FALL_BACK = datetime(2026, 10, 25, tzinfo=BERLIN).date()

#: Дни, когда часы переводят. Именно вокруг них ломается всё интересное.
TRANSITIONS = [
    ("Europe/Berlin", datetime(2026, 3, 29, tzinfo=UTC), time(2, 30)),
    ("Europe/Berlin", datetime(2026, 10, 25, tzinfo=UTC), time(2, 30)),
    ("America/New_York", datetime(2026, 3, 8, tzinfo=UTC), time(1, 30)),
    ("America/New_York", datetime(2026, 11, 1, tzinfo=UTC), time(1, 30)),
    ("Australia/Adelaide", datetime(2026, 4, 5, tzinfo=UTC), time(2, 30)),
    ("America/Santiago", datetime(2026, 9, 6, tzinfo=UTC), time(0, 0)),
]


def test_of_sorts_slots_and_drops_duplicates() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(18, 0), time(9, 0), time(9, 0)])

    assert schedule.slots_on(Weekday.MONDAY) == (time(9, 0), time(18, 0))
    assert schedule.posts_per_week == 14


def test_constructor_refuses_unsorted_slots() -> None:
    week = tuple((time(18, 0), time(9, 0)) if day is Weekday.MONDAY else () for day in Weekday)

    with pytest.raises(InvalidValueError, match=r"MONDAY.*по возрастанию"):
        PublicationSchedule(BERLIN, week)


def test_schedule_without_slots_is_rejected() -> None:
    """Канал, который молчит всегда, — это не расписание, а ошибка настройки"""
    with pytest.raises(InvalidValueError, match="молчит всегда"):
        PublicationSchedule.of("Europe/Berlin", [])


def test_week_of_the_wrong_length_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="в неделе"):
        PublicationSchedule(BERLIN, ((time(9, 0),),))


def test_slot_carrying_its_own_timezone_is_rejected() -> None:
    """Часовой пояс у расписания один, иначе непонятно, кто главнее"""
    week = tuple((time(9, 0, tzinfo=UTC),) if day is Weekday.MONDAY else () for day in Weekday)

    with pytest.raises(InvalidValueError, match="время суток"):
        PublicationSchedule(BERLIN, week)


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


def test_wall_clock_check_wants_a_bare_reading() -> None:
    """Вопрос о показаниях часов, а не о моменте: у момента они есть всегда"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(9, 0)])

    with pytest.raises(InvalidValueError, match="без часового пояса"):
        schedule.wall_clock_exists(datetime(2026, 5, 1, 9, 0, tzinfo=UTC))


def test_reading_inside_the_lost_hour_does_not_exist() -> None:
    """Весной часы прыгают с 02:00 на 03:00 — времени 02:30 в этот день нет"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])

    assert not schedule.wall_clock_exists(datetime.combine(SPRING_FORWARD, time(2, 30)))
    assert schedule.wall_clock_exists(
        datetime.combine(SPRING_FORWARD + timedelta(days=1), time(2, 30))
    )


def test_two_slots_never_collapse_into_one_moment_on_the_transition_day() -> None:
    """Без проверки на существование слоты 02:30 и 03:30 указывали бы на одну секунду"""
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


def test_slot_lost_tomorrow_is_found_the_day_after() -> None:
    """Окна в двое суток не хватало: спрос накануне перехода приводил к отказу"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])

    following = schedule.next_slot_after(
        datetime.combine(SPRING_FORWARD - timedelta(days=1), time(3, 0), tzinfo=BERLIN)
    )

    assert following.date() == SPRING_FORWARD + timedelta(days=1)


def test_timezone_switching_at_midnight_does_not_break_the_scheduler() -> None:
    """Чили переводит часы в 24:00 — полуночного слота в этот день нет вовсе"""
    schedule = PublicationSchedule.of("America/Santiago", [time(0, 0)])
    santiago = ZoneInfo("America/Santiago")

    following = schedule.next_slot_after(datetime(2026, 9, 5, 12, 0, tzinfo=santiago))

    assert following > datetime(2026, 9, 5, 12, 0, tzinfo=santiago)


def test_repeated_hour_in_autumn_gives_one_publication_not_two() -> None:
    """Осенью 02:30 наступает дважды, но пост выходит один раз"""
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])

    first = schedule.next_slot_after(datetime.combine(FALL_BACK, time(0, 0), tzinfo=BERLIN))
    second = schedule.next_slot_after(first)

    assert first.date() == FALL_BACK
    assert second.date() == FALL_BACK + timedelta(days=1)


def test_answer_is_never_in_the_past_inside_the_repeated_hour() -> None:
    """Ошибка, которую не поймал годовой прогон, скармливавший функции её же вывод

    Внутри повторяющегося часа момент имеет fold=1, а собранный слот — fold=0.
    Сравнение двух aware-datetime с одним и тем же поясом идёт по настенным
    часам и fold игнорирует (PEP 495), поэтому уже прошедший слот считался
    будущим. Планировщик после перезапуска публиковал бы пост второй раз.
    """
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30)])
    moment = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)

    assert moment.astimezone(BERLIN).fold == 1
    assert schedule.next_slot_after(moment).astimezone(UTC) > moment


@pytest.mark.parametrize(("zone", "around", "slot"), TRANSITIONS)
def test_answer_is_always_strictly_later_around_a_transition(
    zone: str, around: datetime, slot: time
) -> None:
    """Свойство, которое обязано держаться всегда"""
    schedule = PublicationSchedule.of(zone, [slot])

    moment = around - timedelta(hours=12)
    finish = around + timedelta(hours=36)

    while moment < finish:
        following = schedule.next_slot_after(moment)
        assert following.astimezone(UTC) > moment, f"{zone}: ответ не позже запроса {moment}"
        moment += timedelta(minutes=15)


def test_a_year_of_slots_never_repeats_a_moment() -> None:
    schedule = PublicationSchedule.of("Europe/Berlin", [time(2, 30), time(3, 30), time(14, 0)])

    moment = datetime(2026, 1, 1, tzinfo=BERLIN)
    instants: list[datetime] = []
    while moment.year == 2026:
        moment = schedule.next_slot_after(moment)
        instants.append(moment.astimezone(UTC))

    assert instants == sorted(instants)
    assert len(set(instants)) == len(instants)


def test_channel_can_live_by_a_weekly_rhythm() -> None:
    """Будни и выходные у новостного канала устроены по-разному"""
    schedule = PublicationSchedule.by_weekday(
        "Europe/Berlin",
        {
            Weekday.MONDAY: [time(9, 0), time(18, 0)],
            Weekday.TUESDAY: [time(9, 0), time(18, 0)],
            Weekday.WEDNESDAY: [time(9, 0), time(18, 0)],
            Weekday.THURSDAY: [time(9, 0), time(18, 0)],
            Weekday.FRIDAY: [time(9, 0), time(18, 0)],
            Weekday.SATURDAY: [time(12, 0)],
        },
    )

    assert schedule.posts_per_week == 11
    assert schedule.slots_on(Weekday.SATURDAY) == (time(12, 0),)
    assert schedule.is_silent_on(Weekday.SUNDAY)
    assert not schedule.is_silent_on(Weekday.MONDAY)


def test_silent_days_are_skipped_not_filled() -> None:
    """Воскресенье пропускается целиком, а не подменяется ближайшим слотом"""
    schedule = PublicationSchedule.by_weekday("Europe/Berlin", {Weekday.SATURDAY: [time(12, 0)]})
    saturday = datetime(2026, 5, 2, 12, 0, tzinfo=BERLIN)

    assert saturday.weekday() == Weekday.SATURDAY
    assert schedule.next_slot_after(saturday) == datetime(2026, 5, 9, 12, 0, tzinfo=BERLIN)


def test_weekly_channel_survives_losing_its_slot_to_the_clock_change() -> None:
    schedule = PublicationSchedule.by_weekday("Europe/Berlin", {Weekday.SUNDAY: [time(2, 30)]})
    monday = datetime(2026, 3, 23, 0, 0, tzinfo=BERLIN)

    following = schedule.next_slot_after(monday)

    assert SPRING_FORWARD.weekday() == Weekday.SUNDAY
    assert following == datetime(2026, 4, 5, 2, 30, tzinfo=BERLIN)
    assert (following.date() - monday.date()).days == 13

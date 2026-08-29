"""Тесты тегов"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.tags import MAX_TAG_LENGTH, Tag


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("#нейросети", "нейросети"),
        ("  #AI  ", "ai"),
        ("Machine_Learning", "machine_learning"),
        ("##двойная", "двойная"),
        ("# отбитый пробел", None),
    ],
)
def test_parse_brings_input_to_canonical_form(raw: str, expected: str | None) -> None:
    """То, что приходит от человека и от модели, выглядит по-разному"""
    if expected is None:
        with pytest.raises(InvalidValueError):
            Tag.parse(raw)
    else:
        assert Tag.parse(raw).value == expected


def test_case_is_dropped_so_statistics_do_not_split() -> None:
    """#AI и #ai — один тег, иначе счётчики разъедутся"""
    assert Tag.parse("#AI") == Tag.parse("#ai")


def test_constructor_refuses_non_canonical_value() -> None:
    """Собрать невалидный тег в обход parse не выйдет"""
    with pytest.raises(InvalidValueError, match="нижнем регистре"):
        Tag("AI")


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("", "пустым"),
        ("#", "пустым"),
        ("тег-с-дефисом", "буквы, цифры"),
        ("тег с пробелом", "буквы, цифры"),
        ("2026", "без единой буквы"),
        ("_" * 3, "без единой буквы"),
    ],
)
def test_invalid_tags_are_rejected(raw: str, reason: str) -> None:
    with pytest.raises(InvalidValueError, match=reason):
        Tag.parse(raw)


def test_too_long_tag_is_rejected() -> None:
    with pytest.raises(InvalidValueError, match="длиннее"):
        Tag.parse("a" * (MAX_TAG_LENGTH + 1))


def test_any_language_is_allowed() -> None:
    """Проект настраивается под любой канал, значит и под любой язык"""
    assert Tag.parse("#машинное_обучение").value == "машинное_обучение"
    assert Tag.parse("#機械学習").value == "機械学習"


def test_string_form_is_ready_for_publication() -> None:
    assert str(Tag.parse("нейросети")) == "#нейросети"

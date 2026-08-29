"""Тесты языка канала"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.language import Language


@pytest.mark.parametrize(("raw", "expected"), [("ru", "ru"), (" EN ", "en"), ("Kaz", "kaz")])
def test_parse_is_forgiving_about_case_and_spaces(raw: str, expected: str) -> None:
    assert Language.parse(raw).code == expected


@pytest.mark.parametrize("raw", ["r", "russian", "ру", "e1", ""])
def test_codes_outside_iso_639_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidValueError):
        Language.parse(raw)


def test_constructor_refuses_non_canonical_value() -> None:
    with pytest.raises(InvalidValueError, match="нижнем регистре"):
        Language("RU")


def test_string_form_is_the_bare_code() -> None:
    assert str(Language("ru")) == "ru"

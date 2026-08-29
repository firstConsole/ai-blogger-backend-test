"""Тесты идентификаторов"""

from __future__ import annotations

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.identifiers import ChannelId, PostId, TopicId


def test_new_identifiers_do_not_repeat() -> None:
    assert PostId.new() != PostId.new()


def test_identifier_survives_a_round_trip_through_string() -> None:
    identifier = PostId.new()

    assert PostId.parse(str(identifier)) == identifier


def test_identifiers_of_different_entities_never_match() -> None:
    shared = PostId.new().value

    assert PostId(shared) != ChannelId(shared)  # type: ignore[comparison-overlap]
    assert PostId(shared) != TopicId(shared)  # type: ignore[comparison-overlap]


def test_garbage_string_is_rejected_with_a_domain_error() -> None:
    with pytest.raises(InvalidValueError, match="не похоже на идентификатор"):
        PostId.parse("определённо не uuid")


def test_domain_error_is_also_a_value_error() -> None:
    """Снаружи домена такую ошибку ловят привычным способом"""
    with pytest.raises(ValueError, match="не похоже"):
        PostId.parse("---")


def test_identifier_is_immutable_and_hashable() -> None:
    identifier = PostId.new()

    assert identifier in {identifier}
    with pytest.raises(AttributeError):
        identifier.value = ChannelId.new().value  # type: ignore[misc]

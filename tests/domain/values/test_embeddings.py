"""Тесты эмбеддингов и правила дубликата"""

from __future__ import annotations

import math
import random

import pytest

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.embeddings import (
    DEDUPLICATION_WINDOW,
    DUPLICATE_THRESHOLD,
    Embedding,
)


def test_of_brings_the_vector_to_unit_length() -> None:
    embedding = Embedding.of([3.0, 4.0])

    assert embedding.values == (0.6, 0.8)
    assert math.isclose(math.hypot(*embedding.values), 1.0)
    assert embedding.dimension == 2


def test_constructor_refuses_a_vector_of_the_wrong_length() -> None:
    with pytest.raises(InvalidValueError, match="единичной длины"):
        Embedding((3.0, 4.0))


def test_empty_vector_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="ничего не описывает"):
        Embedding.of([])


@pytest.mark.parametrize("broken", [float("nan"), float("inf"), float("-inf")])
def test_broken_numbers_are_refused(broken: float) -> None:
    """NaN отравил бы сравнение молча: любое сравнение с ним ложно"""
    with pytest.raises(InvalidValueError, match="NaN или бесконечность"):
        Embedding.of([1.0, broken])


def test_zero_vector_is_refused() -> None:
    """Косинус к нулевому вектору не определён — делить не на что"""
    with pytest.raises(InvalidValueError, match="нулевой вектор"):
        Embedding.of([0.0, 0.0, 0.0])


def test_identical_titles_are_perfectly_similar() -> None:
    embedding = Embedding.of([1.0, 2.0, 3.0])

    assert embedding.cosine_similarity(embedding) == pytest.approx(1.0)


def test_opposite_and_orthogonal_vectors() -> None:
    first = Embedding.of([1.0, 0.0])

    assert first.cosine_similarity(Embedding.of([-1.0, 0.0])) == -1.0
    assert first.cosine_similarity(Embedding.of([0.0, 1.0])) == pytest.approx(0.0)


def test_similarity_never_escapes_its_range() -> None:
    generator = random.Random(7)  # noqa: S311 — тестовые данные, а не криптография

    for _ in range(500):
        vector = Embedding.of(generator.uniform(-1, 1) for _ in range(384))
        similarity = vector.cosine_similarity(vector)
        assert -1.0 <= similarity <= 1.0
        assert similarity == pytest.approx(1.0)


def test_vectors_from_different_models_are_not_compared() -> None:
    """Разная размерность — признак того, что заголовки считали разными моделями"""
    with pytest.raises(InvalidValueError, match="разной размерности"):
        Embedding.of([1.0, 0.0]).cosine_similarity(Embedding.of([1.0, 0.0, 0.0]))


def test_duplicate_decision_follows_the_threshold() -> None:
    first = Embedding.of([1.0, 0.0])
    close = Embedding.of([1.0, 0.1])
    distant = Embedding.of([0.0, 1.0])

    assert first.is_duplicate_of(close)
    assert not first.is_duplicate_of(distant)
    assert first.is_duplicate_of(distant, threshold=-1.0)


def test_threshold_outside_the_range_is_refused() -> None:
    with pytest.raises(InvalidValueError, match="между -1 и 1"):
        Embedding.of([1.0, 0.0]).is_duplicate_of(Embedding.of([1.0, 0.0]), threshold=1.5)


def test_deduplication_window_matches_the_plan() -> None:
    """Трое суток из ТЗ: дальше та же новость — уже возвращение к теме"""
    assert DEDUPLICATION_WINDOW.total_seconds() == 72 * 3600
    assert 0.0 < DUPLICATE_THRESHOLD < 1.0

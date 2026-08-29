"""Эмбеддинги заголовков и правило дубликата"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import InvalidValueError

if TYPE_CHECKING:
    from collections.abc import Iterable

DEDUPLICATION_WINDOW = timedelta(hours=72)
DUPLICATE_THRESHOLD = 0.85
UNIT_LENGTH_TOLERANCE = 1e-6
"""Насколько длина вектора может отличаться от единицы.

Допуск задан не «на глаз», а под хранилище. pgvector держит координаты в
float4, и вектор, записанный и прочитанный обратно, приходит слегка другим:
на 384 измерениях длина уплывает до 8e-9. С допуском 1e-9 такой вектор
забраковал бы сам себя при первом же чтении из базы. Замерено кругом через
float4 на трёх тысячах случайных векторов.
"""


@dataclass(frozen=True, slots=True)
class Embedding:
    """Вектор заголовка для поиска похожих тем и дубликатов"""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise InvalidValueError("пустой вектор ничего не описывает")
        if not all(math.isfinite(value) for value in self.values):
            raise InvalidValueError("в векторе есть NaN или бесконечность")

        length = math.hypot(*self.values)
        if not math.isclose(length, 1.0, abs_tol=UNIT_LENGTH_TOLERANCE):
            raise InvalidValueError(
                f"вектор должен быть единичной длины, получена {length:.6f}; используйте of"
            )

    @classmethod
    def of(cls, values: Iterable[float]) -> Self:
        """Привести к единичной длине то, что вернула модель"""
        vector = tuple(float(value) for value in values)
        if not vector:
            raise InvalidValueError("пустой вектор ничего не описывает")
        if not all(math.isfinite(value) for value in vector):
            raise InvalidValueError("в векторе есть NaN или бесконечность")

        length = math.hypot(*vector)
        if length == 0.0:
            raise InvalidValueError("нулевой вектор: близость к нему не определена")
        return cls(tuple(value / length for value in vector))

    @property
    def dimension(self) -> int:
        """Размерность вектора — своя у каждой модели"""
        return len(self.values)

    def cosine_similarity(self, other: Embedding) -> float:
        if self.dimension != other.dimension:
            raise InvalidValueError(
                f"векторы разной размерности: {self.dimension} и {other.dimension}; "
                "скорее всего, заголовки считали разными моделями"
            )
        return max(-1.0, min(1.0, math.sumprod(self.values, other.values)))

    def is_duplicate_of(self, other: Embedding, threshold: float = DUPLICATE_THRESHOLD) -> bool:
        """Считать ли эти заголовки одной темой"""
        if not -1.0 <= threshold <= 1.0:
            raise InvalidValueError(f"порог близости лежит между -1 и 1, получен {threshold}")
        return self.cosine_similarity(other) >= threshold

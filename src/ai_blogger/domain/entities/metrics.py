"""История показателей опубликованного поста"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from ai_blogger.domain.errors import InvalidValueError
from ai_blogger.domain.values.metrics import MEASUREMENT_OFFSETS

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from ai_blogger.domain.values.identifiers import PostId
    from ai_blogger.domain.values.metrics import MetricsSnapshot


@dataclass(eq=False, slots=True)
class PostMetrics:
    """Кривая жизни поста, собранная из отдельных замеров

    Заводится в момент публикации: до неё измерять нечего. Дальше воркер
    добавляет замеры по расписанию, а планировщик спрашивает, когда следующий.
    """

    post_id: PostId
    published_at: datetime
    snapshots: tuple[MetricsSnapshot, ...] = ()

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None:
            raise InvalidValueError("время публикации без часового пояса ни с чем не сравнить")

    @classmethod
    def start(cls, *, post_id: PostId, published_at: datetime) -> Self:
        """Начать наблюдение за только что опубликованным постом"""
        return cls(post_id=post_id, published_at=published_at)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PostMetrics):
            return NotImplemented
        return self.post_id == other.post_id

    def __hash__(self) -> int:
        return hash(self.post_id)

    @property
    def latest(self) -> MetricsSnapshot | None:
        """Последний по плану замер"""
        return self.snapshots[-1] if self.snapshots else None

    @property
    def pending_offsets(self) -> tuple[timedelta, ...]:
        """Замеры, которые ещё предстоит снять"""
        taken = {snapshot.offset for snapshot in self.snapshots}
        return tuple(offset for offset in MEASUREMENT_OFFSETS if offset not in taken)

    @property
    def is_complete(self) -> bool:
        """Все запланированные замеры сняты"""
        return not self.pending_offsets

    @property
    def next_due_at(self) -> datetime | None:
        """Когда снимать следующий замер"""
        pending = self.pending_offsets
        return self.published_at + pending[0] if pending else None

    def record(self, snapshot: MetricsSnapshot) -> None:
        """Добавить замер

        Просмотры и пересылки обязаны расти. Telegram их не уменьшает, поэтому
        падение счётчика означает не спад интереса, а сломанный сбор: не тот
        номер сообщения, пост пересоздали, ответ пришёл от другого поста. Такой
        замер лучше отвергнуть громко, чем сохранить и потом строить по нему
        выводы. С реакциями иначе — их снимают, и уменьшение там нормально.
        """
        if snapshot.offset not in self.pending_offsets:
            raise InvalidValueError(f"замер через {snapshot.offset} уже снят")
        if snapshot.measured_at < self.published_at:
            raise InvalidValueError("замер сделан раньше публикации")

        previous = self.latest
        if previous is not None:
            _check_growth("просмотры", previous.views, snapshot.views)
            _check_growth("пересылки", previous.forwards, snapshot.forwards)

        self.snapshots = (*self.snapshots, snapshot)

    def delay_of(self, snapshot: MetricsSnapshot) -> timedelta:
        """Насколько замер опоздал против плана

        Очередь, перезапуск воркера и недоступный Telegram сдвигают замер, и без
        этой величины непонятно, сравниваем мы час с часом или час с тремя.
        """
        return snapshot.measured_at - (self.published_at + snapshot.offset)


def _check_growth(name: str, previous: int, current: int) -> None:
    if current < previous:
        raise InvalidValueError(
            f"{name}: было {previous}, стало {current} — счётчик не мог убыть, "
            "скорее всего замер снят не с того сообщения"
        )

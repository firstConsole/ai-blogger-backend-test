"""Единица работы"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from types import TracebackType


class UnitOfWork(Protocol):
    """Границы транзакции"""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None:
        """Зафиксировать изменения"""
        ...

    async def rollback(self) -> None:
        """Откатить изменения"""
        ...

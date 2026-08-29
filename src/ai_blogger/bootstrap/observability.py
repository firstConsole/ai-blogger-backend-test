from __future__ import annotations

from typing import TYPE_CHECKING

from ai_blogger.infrastructure.observability.logs import configure_logging

if TYPE_CHECKING:
    from ai_blogger.bootstrap.config import Settings


def setup_observability(settings: Settings) -> None:
    """Включает логи и трассировку для приложения"""
    configure_logging(
        level=settings.observability.log_level,
        log_format=settings.observability.log_format,
    )

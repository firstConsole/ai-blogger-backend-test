"""Базовые ошибки домена"""


class DomainError(Exception): ...


class InvalidValueError(DomainError, ValueError):
    """Значение не проходит правила предметной области"""


class IllegalTransitionError(DomainError):
    """Попытка перевести сущность в состояние, недостижимое из текущего"""

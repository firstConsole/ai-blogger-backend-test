"""Базовые ошибки домена"""


class DomainError(Exception): ...


class InvalidValueError(DomainError, ValueError):
    """Значение не проходит правила предметной области

    Наследуется и от ValueError: снаружи такую ошибку ловят привычным способом,
    а внутри домена — как DomainError, не зная про конкретный тип значения.
    """

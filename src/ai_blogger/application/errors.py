"""Ошибки уровня приложения"""


class ApplicationError(Exception):
    """Сценарий не может быть выполнен. Корень иерархии этого слоя"""


class EntityNotFoundError(ApplicationError):
    """Объект, с которым собирались работать, отсутствует"""


class AccessDeniedError(ApplicationError):
    """У вызывающего нет прав на это действие"""


class ExternalServiceError(ApplicationError):
    """Внешний сервис недоступен"""

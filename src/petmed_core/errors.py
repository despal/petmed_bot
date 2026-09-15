class CoreError(Exception):
    """Явная ошибка команды ядра."""


class PermissionDenied(CoreError):
    pass


class NotFound(CoreError):
    pass


class ValidationError(CoreError):
    pass

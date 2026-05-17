class UserNotFoundError(Exception): ...


class PredictionError(Exception): ...


class DatabaseUnavailableError(Exception):
    """База данных временно недоступна"""


class RepositoryError(Exception):
    """Неожиданная ошибка в репозитории"""

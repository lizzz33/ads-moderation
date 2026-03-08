import time
from functools import wraps

from prometheus_client import Counter, Histogram

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total", "Total number of HTTP errors", ["status_code", "method", "handler"]
)

PREDICTIONS_TOTAL = Counter("predictions_total", "Total number of predictions", ["result"])

PREDICTION_DURATION = Histogram(
    "prediction_duration_seconds",
    "Time spent on ML model inference",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

PREDICTION_ERRORS_TOTAL = Counter(
    "prediction_errors_total",
    "Total number of prediction errors",
    ["error_type"],
)

DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Time spent on PostgreSQL queries",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

MODEL_PREDICTION_PROBABILITY = Histogram(
    "model_prediction_probability",
    "Distribution of prediction probabilities",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)


def track_prediction_duration(func):
    """Декоратор для замера времени инференса модели"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start
            PREDICTION_DURATION.observe(duration)

    return wrapper


def track_db_query(query_type):
    """Декоратор для замера времени запросов к БД"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start
                DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

        return wrapper

    return decorator

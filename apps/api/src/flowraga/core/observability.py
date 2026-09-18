import logging
import time

import structlog
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "flowraga_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "flowraga_http_request_duration_seconds", "HTTP request latency", ["method", "route"]
)
AI_OPERATIONS = Counter("flowraga_ai_operations_total", "AI operations", ["operation", "status"])
AI_DURATION = Histogram(
    "flowraga_ai_operation_duration_seconds", "AI operation latency", ["operation"]
)


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO), format="%(message)s"
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def observe_request(method: str, route: str, status: int, started: float) -> None:
    HTTP_REQUESTS.labels(method=method, route=route, status=str(status)).inc()
    HTTP_DURATION.labels(method=method, route=route).observe(time.perf_counter() - started)


def observe_ai_operation(operation: str, status: str, duration_seconds: float) -> None:
    AI_OPERATIONS.labels(operation=operation, status=status).inc()
    AI_DURATION.labels(operation=operation).observe(duration_seconds)

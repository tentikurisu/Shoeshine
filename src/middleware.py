"""Middleware module for logging and metrics."""

import logging
import os
import time
from typing import Dict, List
from contextlib import contextmanager


def setup_logging() -> logging.Logger:
    """Setup logging configuration."""
    logger = logging.getLogger("shoeshine")

    # Remove existing handlers
    logger.handlers.clear()

    # Set log level
    logger.setLevel(logging.INFO)

    # Check if running in AWS Lambda
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        # JSON logging for Lambda
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '{"level": "%(levelname)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
    else:
        # Console logging for local development
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def get_metrics():
    """Get the global metrics collector instance."""
    return _global_metrics


_global_metrics = None


class MetricsCollector:
    """Collector for application metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, List[float]] = {}
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0

    def increment(self, name: str, value: int = 1):
        """Increment a counter metric."""
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += value

    def counter_value(self, name: str) -> int:
        """Get the value of a counter metric."""
        return self._counters.get(name, 0)

    def timing(self, name: str, value: float):
        """Record a timing metric in milliseconds."""
        if name not in self._timers:
            self._timers[name] = []
        self._timers[name].append(value)

    def timer_values(self, name: str) -> List[float]:
        """Get all values for a timer metric."""
        return self._timers.get(name, [])

    def get_summary(self):
        """Get metrics summary."""
        total_requests = self._counters.get("requests", 0)
        return type(
            "obj",
            (object,),
            {
                "request_count": total_requests,
                "success_count": self._success_count,
                "error_count": self._error_count,
            },
        )()

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        lines = []

        # Counters
        for name, value in self._counters.items():
            lines.append(f"# HELP shoeshine_{name}_total Total {name}")
            lines.append(f"# TYPE shoeshine_{name}_total counter")
            lines.append(f"shoeshine_{name}_total {value}")

        # Timers (average)
        for name, values in self._timers.items():
            if values:
                avg = sum(values) / len(values)
                lines.append(f"# HELP shoeshine_{name}_ms_avg Average {name} in ms")
                lines.append(f"# TYPE shoeshine_{name}_ms_avg gauge")
                lines.append(f"shoeshine_{name}_ms_avg {avg:.2f}")

        return "\n".join(lines)

    def reset(self):
        """Reset all metrics."""
        self._counters.clear()
        self._timers.clear()
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0


class RequestMetrics:
    """Context manager for tracking request metrics."""

    def __init__(self, metrics: MetricsCollector):
        """Initialize request metrics tracker."""
        self.metrics = metrics
        self.start_time = None
        self.request_id = None

    def start(self, request_id: str, path: str):
        """Start tracking a request."""
        self.request_id = request_id
        self.start_time = time.time()
        self.metrics.increment("requests")

    def end(self, success: bool = True, **kwargs):
        """End tracking a request and record metrics."""
        if self.start_time is None:
            return 0.0

        duration = (time.time() - self.start_time) * 1000  # Convert to ms
        self.metrics.timing("request_duration", duration)

        if success:
            self.metrics._success_count += 1
        else:
            self.metrics._error_count += 1

        return duration


# Initialize global metrics collector
_global_metrics = MetricsCollector()

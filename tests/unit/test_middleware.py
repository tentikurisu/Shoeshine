"""Unit tests for Shoeshine middleware."""

import pytest
import logging
import time
import os

from src.middleware import (
    setup_logging,
    get_metrics,
    RequestMetrics,
    MetricsCollector,
)

from src.services.auth_service import RateLimiter


class TestLogging:
    """Tests for logging middleware."""

    def test_setup_logging_json(self, monkeypatch):
        """Test JSON logging setup."""
        monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "test")

        logger = setup_logging()
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1

    def test_setup_logging_console(self):
        """Test console logging setup."""
        logger = setup_logging()
        # Default level is INFO
        assert logger.level == logging.INFO


class TestMetrics:
    """Tests for metrics middleware."""

    def test_metrics_collector(self):
        """Test metrics collector operations."""
        metrics = MetricsCollector()

        # Increment counter
        metrics.increment("requests")
        metrics.increment("requests", 2)

        assert metrics.counter_value("requests") == 3

        # Record timing
        metrics.timing("processing", 100.5)
        metrics.timing("processing", 200.0)

        timer_values = metrics.timer_values("processing")
        assert len(timer_values) == 2

        # Get summary
        summary = metrics.get_summary()
        assert summary.request_count == 3

    def test_metrics_prometheus_format(self):
        """Test Prometheus metrics output format."""
        metrics = MetricsCollector()
        metrics.increment("requests")
        metrics.timing("test_operation", 50.0)

        output = metrics.get_prometheus_metrics()

        assert "shoeshine_requests_total" in output
        assert "shoeshine_test_operation_ms_avg" in output
        assert "# HELP" in output
        assert "# TYPE" in output

    def test_metrics_reset(self):
        """Test metrics reset."""
        metrics = MetricsCollector()
        metrics.increment("requests")
        metrics.timing("test", 100.0)

        metrics.reset()

        assert metrics.counter_value("requests") == 0
        assert metrics.timer_values("test") == []

    def test_request_metrics(self):
        """Test request metrics tracking."""
        metrics = MetricsCollector()
        request_metrics = RequestMetrics(metrics)

        request_metrics.start("req-123", "/extract/text")
        duration = request_metrics.end(success=True, extraction_type="text")

        assert duration >= 0
        summary = metrics.get_summary()
        assert summary.request_count == 1
        assert summary.success_count == 1


class TestRateLimiter:
    """Tests for rate limiter."""

    def test_rate_limit(self):
        """Test rate limiting."""
        from src.services.auth_service import RateLimiter

        limiter = RateLimiter(requests_per_minute=5)

        # First 5 requests should be allowed for the same user
        for i in range(5):
            assert limiter.is_allowed("same-user") is True

        # 6th request should be blocked for the same user
        assert limiter.is_allowed("same-user") is False

    def test_rate_limit_remaining(self):
        """Test getting remaining requests."""
        from src.services.auth_service import RateLimiter

        limiter = RateLimiter(requests_per_minute=3)

        assert limiter.get_remaining("user-1") == 3

        limiter.is_allowed("user-1")
        limiter.is_allowed("user-1")
        limiter.is_allowed("user-1")

        assert limiter.get_remaining("user-1") == 0

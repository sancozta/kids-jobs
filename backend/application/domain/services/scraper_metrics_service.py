"""
Scraper Metrics Service
Maintains per-scraper runtime metrics and Prometheus counters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from prometheus_client import Counter, Gauge

RUNS_TOTAL = Counter(
    "h_scraping_scraper_runs_total",
    "Total scraper runs by scraper/status",
    ["scraper", "status"],
)
ITEMS_TOTAL = Counter(
    "h_scraping_scraper_items_total",
    "Total items scraped/published by scraper",
    ["scraper"],
)
ERRORS_TOTAL = Counter(
    "h_scraping_scraper_errors_total",
    "Total scraper execution errors",
    ["scraper"],
)
LAST_SUCCESS_TS = Gauge(
    "h_scraping_scraper_last_success_timestamp",
    "Unix timestamp of the last successful scraper run",
    ["scraper"],
)


@dataclass
class ScraperMetricState:
    runs_total: int = 0
    items_total: int = 0
    errors_total: int = 0
    last_success_at: Optional[datetime] = None


class ScraperMetricsService:
    """Thread-safe per-scraper metrics registry."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict[str, ScraperMetricState] = {}

    def _get_or_create(self, scraper_name: str) -> ScraperMetricState:
        if scraper_name not in self._state:
            self._state[scraper_name] = ScraperMetricState()
        return self._state[scraper_name]

    def record_success(self, scraper_name: str, items_count: int) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            state = self._get_or_create(scraper_name)
            state.runs_total += 1
            state.items_total += max(items_count, 0)
            state.last_success_at = now

        RUNS_TOTAL.labels(scraper=scraper_name, status="success").inc()
        ITEMS_TOTAL.labels(scraper=scraper_name).inc(max(items_count, 0))
        LAST_SUCCESS_TS.labels(scraper=scraper_name).set(now.timestamp())

    def record_error(self, scraper_name: str) -> None:
        with self._lock:
            state = self._get_or_create(scraper_name)
            state.runs_total += 1
            state.errors_total += 1

        RUNS_TOTAL.labels(scraper=scraper_name, status="error").inc()
        ERRORS_TOTAL.labels(scraper=scraper_name).inc()

    def snapshot(self) -> dict[str, dict[str, Optional[str] | int]]:
        with self._lock:
            items = sorted(self._state.items())

        return {
            name: {
                "runs_total": state.runs_total,
                "items_total": state.items_total,
                "errors_total": state.errors_total,
                "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
            }
            for name, state in items
        }

"""Smoke tests for real scraper connectivity/extraction."""
from __future__ import annotations

import os

import pytest

from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.services.scraper_factory import ScraperFactory
from application.domain.services.scraper_registry import ScraperRegistry


def _targets() -> list[str]:
    raw = (os.getenv("SCRAPER_SMOKE_TARGETS") or "").strip()
    if not raw or raw.lower() == "all":
        return sorted(ScraperRegistry.get_all_scrapers().keys())
    return [item.strip() for item in raw.split(",") if item.strip()]


@pytest.mark.smoke
def test_smoke_scrapers_return_items_without_block() -> None:
    if os.getenv("RUN_SCRAPER_SMOKE") != "1":
        pytest.skip("Set RUN_SCRAPER_SMOKE=1 to enable real-network smoke tests")

    load_all_scrapers()

    failures: list[str] = []

    for scraper_name in _targets():
        scraper = ScraperFactory.create(scraper_name)
        if scraper is None:
            failures.append(f"{scraper_name}: scraper not found in registry")
            continue

        items = scraper.scrape()
        diagnostics = getattr(scraper, "last_fetch_diagnostics", {}) or {}

        if diagnostics.get("blocked"):
            failures.append(
                f"{scraper_name}: blocked by target site (status={diagnostics.get('status_code')})"
            )
            continue

        if len(items) == 0:
            failures.append(f"{scraper_name}: returned 0 items")

    assert not failures, "\\n".join(failures)

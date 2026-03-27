"""
Scraper Execution Service
Centralizes single-source execution for scheduler/manual runs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from adapters.outbound.messaging.local_ingest_adapter import LocalIngestAdapter
from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.entities.scraper_config import ScraperConfig
from application.domain.entities.source import Source
from application.domain.services.scraper_factory import ScraperFactory
from application.domain.services.scraper_metrics_service import ScraperMetricsService
from application.domain.services.scraper_registry import ScraperRegistry
from application.domain.services.scraping_service import ScrapingService, ScraperExecutionSummary
from application.domain.shared.scraper_types import ScrapingStrategy
from configuration.settings_configuration import settings


@dataclass
class SourceExecutionResult:
    source_id: int
    source_name: str
    success: bool
    scraped_count: int
    published_count: int
    duration_ms: int
    strategy: str
    http_status_code: Optional[int] = None
    error: Optional[str] = None


class ScraperExecutionService:
    """Executes scraper runs for a configured source."""

    def __init__(self, metrics_service: ScraperMetricsService):
        self.metrics_service = metrics_service

    @staticmethod
    def classify_extraction_status(result: SourceExecutionResult) -> str:
        if result.http_status_code is not None and result.http_status_code != 200:
            return "ERROR"
        if not result.success:
            return "ERROR"
        if result.scraped_count <= 0:
            return "PARTIAL"
        if result.published_count <= 0:
            return "ERROR"
        if result.published_count < result.scraped_count:
            return "PARTIAL"
        if result.scraped_count > 0:
            return "SUCCESS"
        return "PARTIAL"

    @staticmethod
    def build_extraction_message(result: SourceExecutionResult) -> str:
        status = ScraperExecutionService.classify_extraction_status(result)
        if result.error:
            return result.error
        if status == "SUCCESS":
            return f"Extraído e publicado ({result.published_count}/{result.scraped_count} itens)"
        if status == "PARTIAL":
            return f"Extração/publicação parcial ({result.published_count}/{result.scraped_count} itens)"
        if result.http_status_code is not None:
            return f"HTTP {result.http_status_code}"
        return f"Falha na publicação ({result.published_count}/{result.scraped_count} itens)"

    @staticmethod
    def _resolve_strategy(scraper_type: str) -> ScrapingStrategy:
        normalized = (scraper_type or "").strip().lower()
        if normalized in {"http_basic", "basic"}:
            return ScrapingStrategy.HTTP_BASIC
        if normalized in {"http", "http_antibot", "antibot"}:
            return ScrapingStrategy.HTTP_ANTIBOT
        if normalized in {"browser_playwright", "playwright"}:
            return ScrapingStrategy.BROWSER_PLAYWRIGHT
        return ScrapingStrategy.HTTP_BASIC

    @staticmethod
    def _parse_proxy_pool() -> list[str]:
        raw = (settings.scraping_proxy_pool or "").strip()
        if not raw:
            return []
        return [proxy.strip() for proxy in raw.split(",") if proxy.strip()]

    @staticmethod
    def apply_source_overrides_to_config(config: ScraperConfig, source: Source) -> ScrapingStrategy:
        strategy = ScraperExecutionService._resolve_strategy(source.scraper_type)

        if source.scraper_base_url:
            config.base_url = source.scraper_base_url
        config.strategy = strategy
        if source.scraper_schedule:
            config.schedule = source.scraper_schedule

        if isinstance(source.extra_config, dict) and source.extra_config:
            config.extra_config.update(deepcopy(source.extra_config))

        if strategy in {ScrapingStrategy.HTTP_ANTIBOT, ScrapingStrategy.BROWSER_PLAYWRIGHT}:
            proxy_pool = ScraperExecutionService._parse_proxy_pool()
            if proxy_pool:
                config.extra_config["proxy_pool"] = proxy_pool

        return strategy

    def _apply_source_overrides(self, source: Source):
        if not ScraperRegistry.get_all_scrapers():
            load_all_scrapers()

        scraper_name = source.name.strip().lower()
        scraper = ScraperFactory.create(scraper_name)
        if not scraper:
            return None, ScrapingStrategy.HTTP_BASIC

        config = scraper.get_config()
        strategy = ScrapingStrategy.HTTP_BASIC

        if config:
            strategy = self.apply_source_overrides_to_config(config, source)
        else:
            strategy = self._resolve_strategy(source.scraper_type)

        return scraper, strategy

    def execute_source(self, source: Source) -> SourceExecutionResult:
        scraper, strategy = self._apply_source_overrides(source)
        strategy_name = strategy.value

        if not scraper:
            self.metrics_service.record_error(source.name.lower())
            return SourceExecutionResult(
                source_id=source.id or 0,
                source_name=source.name,
                success=False,
                scraped_count=0,
                published_count=0,
                duration_ms=0,
                strategy=strategy_name,
                http_status_code=None,
                error=f"Scraper '{source.name.lower()}' not found in registry",
            )

        try:
            scraping_service = ScrapingService(messaging_port=LocalIngestAdapter(), metrics_service=self.metrics_service)
            summary: ScraperExecutionSummary = scraping_service.execute_scraper(scraper)
            diagnostics = getattr(scraper, "last_fetch_diagnostics", {}) or {}
            raw_status_code = diagnostics.get("status_code") if isinstance(diagnostics, dict) else None
            http_status_code = raw_status_code if isinstance(raw_status_code, int) else None

            return SourceExecutionResult(
                source_id=source.id or 0,
                source_name=source.name,
                success=summary.success,
                scraped_count=summary.scraped_count,
                published_count=summary.published_count,
                duration_ms=summary.duration_ms,
                strategy=strategy_name,
                http_status_code=http_status_code,
                error=summary.error,
            )
        except Exception as exc:
            self.metrics_service.record_error(source.name.lower())
            return SourceExecutionResult(
                source_id=source.id or 0,
                source_name=source.name,
                success=False,
                scraped_count=0,
                published_count=0,
                duration_ms=0,
                strategy=strategy_name,
                http_status_code=None,
                error=str(exc),
            )

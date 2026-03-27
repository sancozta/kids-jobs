"""
Scraping Service — Domain Service
Unified service for executing scrapers and publishing results.
"""
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Optional

from application.domain.entities.scraped_item import ScrapedItem
from application.domain.exceptions.domain_exceptions import PublishException
from application.domain.services.scraper_metrics_service import ScraperMetricsService
from application.ports.outbound.messaging.messaging_port import MessagingPort
from application.ports.outbound.scraping.scraper_port import ScraperPort

logger = logging.getLogger(__name__)


class ScrapingService:
    """Domain service for scraper execution and result publishing"""

    def __init__(self, messaging_port: MessagingPort, metrics_service: Optional[ScraperMetricsService] = None):
        self.messaging_port = messaging_port
        self.metrics_service = metrics_service

    def execute_scraper(self, scraper: ScraperPort) -> "ScraperExecutionSummary":
        """Execute a scraper and publish all results to messaging."""
        scraper_name = scraper.get_name()
        started_at = perf_counter()
        try:
            items = scraper.scrape()
            scraped_count = len(items)

            if not items:
                logger.warning(f"No items from {scraper_name}")
                if self.metrics_service:
                    self.metrics_service.record_success(scraper_name, items_count=0)
                self._update_scraper_stats(scraper, status="success", items_count=0)
                return ScraperExecutionSummary(
                    scraper_name=scraper_name,
                    success=True,
                    scraped_count=0,
                    published_count=0,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )

            published = self.publish_items(items)
            logger.info(f"Published {published}/{scraped_count} items from {scraper_name}")
            if published <= 0:
                logger.error(f"No items were published from {scraper_name} ({published}/{scraped_count})")
                if self.metrics_service:
                    self.metrics_service.record_error(scraper_name)
                self._update_scraper_stats(scraper, status="error", items_count=published)
                return ScraperExecutionSummary(
                    scraper_name=scraper_name,
                    success=False,
                    scraped_count=scraped_count,
                    published_count=published,
                    error="Falha ao persistir itens localmente",
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )

            if self.metrics_service:
                self.metrics_service.record_success(scraper_name, items_count=published)
            self._update_scraper_stats(scraper, status="success", items_count=published)
            return ScraperExecutionSummary(
                scraper_name=scraper_name,
                success=True,
                scraped_count=scraped_count,
                published_count=published,
                duration_ms=int((perf_counter() - started_at) * 1000),
            )

        except Exception as e:
            logger.error(f"Scraper error in {scraper_name}: {e}", exc_info=True)
            if self.metrics_service:
                self.metrics_service.record_error(scraper_name)
            self._update_scraper_stats(scraper, status="error", items_count=0)
            return ScraperExecutionSummary(
                scraper_name=scraper_name,
                success=False,
                scraped_count=0,
                published_count=0,
                error=str(e),
                duration_ms=int((perf_counter() - started_at) * 1000),
            )

    def publish_item(self, item: ScrapedItem) -> None:
        """Publish a single item to messaging"""
        try:
            self.messaging_port.publish(item, routing_key=item.category_name)
        except Exception as e:
            raise PublishException(f"Failed to publish item from '{item.source_name}': {e}") from e

    def publish_items(self, items: list[ScrapedItem]) -> int:
        """Publish multiple items, returning count of successes"""
        published = 0
        for item in items:
            try:
                self.publish_item(item)
                published += 1
            except PublishException as exc:
                logger.warning("Failed to publish item %s: %s", item.url, exc)
                continue
        return published

    @staticmethod
    def _update_scraper_stats(scraper: ScraperPort, status: str, items_count: int) -> None:
        config = scraper.get_config()
        if config:
            config.update_stats(status=status, items_count=items_count)


@dataclass
class ScraperExecutionSummary:
    scraper_name: str
    success: bool
    scraped_count: int
    published_count: int
    duration_ms: int
    error: Optional[str] = None

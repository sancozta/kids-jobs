"""
Scraper Factory — Creates scraper instances from registry.
Domain service — references only ScraperPort (not concrete adapters).
"""
import logging
from typing import Optional

from application.ports.outbound.scraping.scraper_port import ScraperPort
from application.domain.services.scraper_registry import ScraperRegistry
from application.domain.entities.scraper_config import ScraperConfig

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory for creating scraper instances"""

    @staticmethod
    def create(name: str, config: Optional[ScraperConfig] = None) -> Optional[ScraperPort]:
        """
        Create a scraper instance by name.

        Args:
            name:   Registered scraper name
            config: Optional config to override registry config

        Returns:
            Scraper instance or None if not found
        """
        scraper_class = ScraperRegistry.get_scraper_class(name)

        if not scraper_class:
            logger.error(f"Scraper '{name}' not found in registry")
            return None

        scraper_config = config or ScraperRegistry.get_config(name)

        try:
            instance = scraper_class(config=scraper_config) if scraper_config else scraper_class()
            logger.info(f"Created scraper instance: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create scraper '{name}': {e}")
            return None

    @staticmethod
    def create_batch(names: list[str]) -> list[ScraperPort]:
        """Create multiple scraper instances (skips disabled/failed)"""
        instances = []
        for name in names:
            scraper = ScraperFactory.create(name)
            if scraper and scraper.is_enabled():
                instances.append(scraper)
        return instances

    @staticmethod
    def create_by_category(category: str) -> list[ScraperPort]:
        """Create all scrapers for a category"""
        names = ScraperRegistry.get_scrapers_by_category(category)
        return ScraperFactory.create_batch(names)

    @staticmethod
    def create_all_enabled() -> list[ScraperPort]:
        """Create all enabled scrapers"""
        names = ScraperRegistry.get_enabled_scrapers()
        return ScraperFactory.create_batch(names)

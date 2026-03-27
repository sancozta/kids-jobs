"""
Scraper Registry — Central registry for all scrapers.
Domain service — references only ScraperPort (not concrete adapters).
"""
import logging
from typing import Dict, Type, List, Optional

from application.ports.outbound.scraping.scraper_port import ScraperPort
from application.domain.entities.scraper_config import ScraperConfig

logger = logging.getLogger(__name__)


class ScraperRegistry:
    """Singleton registry for managing all available scrapers."""

    _instance = None
    _scrapers: Dict[str, Type[ScraperPort]] = {}
    _configs: Dict[str, ScraperConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, scraper_class: Type[ScraperPort], config: Optional[ScraperConfig] = None):
        """Register a scraper class"""
        if name in cls._scrapers:
            logger.warning(f"Scraper '{name}' already registered, overwriting")

        cls._scrapers[name] = scraper_class
        if config:
            cls._configs[name] = config

        logger.info(f"Registered scraper: {name}")

    @classmethod
    def unregister(cls, name: str):
        """Unregister a scraper"""
        if name in cls._scrapers:
            del cls._scrapers[name]
            cls._configs.pop(name, None)
            logger.info(f"Unregistered scraper: {name}")

    @classmethod
    def get_scraper_class(cls, name: str) -> Optional[Type[ScraperPort]]:
        """Get scraper class by name"""
        return cls._scrapers.get(name)

    @classmethod
    def get_config(cls, name: str) -> Optional[ScraperConfig]:
        """Get scraper config by name"""
        return cls._configs.get(name)

    @classmethod
    def get_all_scrapers(cls) -> Dict[str, Type[ScraperPort]]:
        """Get all registered scrapers"""
        return cls._scrapers.copy()

    @classmethod
    def get_enabled_scrapers(cls) -> List[str]:
        """Get list of enabled scraper names"""
        return [name for name, config in cls._configs.items() if config.enabled]

    @classmethod
    def get_scrapers_by_category(cls, category: str) -> List[str]:
        """Get scrapers by category"""
        return [
            name for name, config in cls._configs.items()
            if config.metadata.category == category
        ]

    @classmethod
    def get_scrapers_by_source_type(cls, source_type: str) -> List[str]:
        """Get scrapers by source type"""
        return [
            name for name, config in cls._configs.items()
            if config.metadata.source_type.value == source_type
        ]

    @classmethod
    def list_all(cls) -> List[dict]:
        """List all scrapers with metadata"""
        result = []
        for name, scraper_class in cls._scrapers.items():
            config = cls._configs.get(name)
            if config:
                result.append({
                    "name": name,
                    "display_name": config.metadata.display_name,
                    "description": config.metadata.description,
                    "category": config.metadata.category,
                    "source_type": config.metadata.source_type.value,
                    "enabled": config.enabled,
                    "version": config.metadata.version,
                    "last_run": config.last_run.isoformat() if config.last_run else None,
                    "last_status": config.last_status,
                    "total_runs": config.total_runs,
                    "total_items": config.total_items_scraped,
                })
            else:
                result.append({
                    "name": name,
                    "class": scraper_class.__name__,
                    "enabled": True,
                })
        return result

    @classmethod
    def clear(cls):
        """Clear all registered scrapers (useful for testing)"""
        cls._scrapers.clear()
        cls._configs.clear()
        logger.info("Registry cleared")

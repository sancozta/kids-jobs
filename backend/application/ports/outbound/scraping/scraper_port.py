"""
Scraper Port — Outbound Port
Defines the contract for all scrapers in the system.
"""
from abc import ABC, abstractmethod
from typing import Optional

from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig


class ScraperPort(ABC):
    """Interface that all scrapers must implement"""

    @abstractmethod
    def scrape(self) -> list[ScrapedItem]:
        """Execute scraping and return items in contract format"""
        ...

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        """Optional single-item scraping entrypoint for rescrape flows."""
        return None

    @abstractmethod
    def get_name(self) -> str:
        """Return unique scraper name for registry"""
        ...

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if scraper is enabled"""
        ...

    @abstractmethod
    def get_config(self) -> Optional[ScraperConfig]:
        """Return scraper configuration"""
        ...

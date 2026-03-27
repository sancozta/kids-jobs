"""
VivaReal Scraper
Scrapes property listings from VivaReal
"""
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class VivaRealScraper(HTTPScraper):
    """Scraper for VivaReal property listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="vivareal",
                display_name="VivaReal",
                description="Scraper de casas à venda do VivaReal em Porto Alegre",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.vivareal.com.br",
            endpoint="/venda/rio-grande-do-sul/porto-alegre/casa_residencial/",
            enabled=True,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            rate_limit_delay=2.5,
            max_items_per_run=50,
            extra_config={
                "playwright_headless": False,
                "playwright_headful_fallback": True,
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3000,
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping VivaReal from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select('div[data-type="property"]')

            for idx, listing in enumerate(listings):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self._parse_listing(listing)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
                    continue

            self.logger.info(f"Scraped {len(items)} items from VivaReal")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping VivaReal: {e}")
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        try:
            title = self.extract_text(listing, 'span[class*="title"]')
            price_text = self.extract_text(listing, 'div[class*="price"]')
            price = self.parse_price(price_text)

            link_elem = listing.select_one("a[href]")
            url = urljoin(self.config.base_url, link_elem.get("href", "")) if link_elem else None
            if not url:
                return None

            area = self.extract_text(listing, 'span[itemprop="floorSize"]')
            bedrooms = self.extract_text(listing, 'li[class*="bedrooms"] span')
            bathrooms = self.extract_text(listing, 'li[class*="bathrooms"] span')
            location = self.extract_text(listing, 'span[class*="address"]')

            scraped_data = {
                "title": title,
                "price": price,
                "currency": "BRL",
                "location": {"raw": location},
                "attributes": {
                    "bedrooms": self.parse_int(bedrooms),
                    "bathrooms": self.parse_int(bathrooms),
                    "area_m2": self.parse_int(area),
},
            }

            return self.build_scraped_item(
                url=url,
                scraped_data=scraped_data,
            )
        except Exception as e:
            self.logger.error(f"Error parsing listing: {e}")
            return None

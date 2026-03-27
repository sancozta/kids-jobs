"""
Kavak Scraper
Scrapes vehicle listings from Kavak Brasil
"""
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class KavakScraper(HTTPScraper):
    """Scraper for Kavak vehicle listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="kavak",
                display_name="Kavak",
                description="Scraper de seminovos da Kavak",
                category=ScrapingCategory.VEHICLES,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.kavak.com",
            endpoint="/br/seminovos",
            enabled=False,
            rate_limit_delay=2.5,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Kavak from: {url}")
            response = self.fetch_page(url)
            if not response:
                return items
            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/br/venda/']")
            seen_urls: set[str] = set()
            for listing in listings:
                href = listing.get("href", "").strip()
                listing_url = urljoin(self.config.base_url, href).split("?")[0]
                if not listing_url or listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                idx = len(items)
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self.scrape_url(listing_url)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
            self.logger.info(f"Scraped {len(items)} items from Kavak")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Kavak: {e}")
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = (url or "").strip()
        if not normalized_url:
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None

        return self._parse_detail_page(normalized_url, response.text)

    def _parse_detail_page(self, url: str, html: str) -> Optional[ScrapedItem]:
        car_data = self._extract_car_ld_json(html)
        if not car_data:
            return None

        soup = self.parse_html(html)
        description = self.extract_attr(soup, "meta[name='description']", "content")
        brand = ((car_data.get("brand") or {}).get("name") if isinstance(car_data.get("brand"), dict) else car_data.get("brand"))
        offers = car_data.get("offers") or {}
        mileage = (car_data.get("mileageFromOdometer") or {}).get("value")

        scraped_data = {
            "title": car_data.get("name"),
            "description": description,
            "price": self.parse_price(str(offers.get("price"))) if offers.get("price") is not None else None,
            "currency": offers.get("priceCurrency") or "BRL",
            "images": list(car_data.get("image") or []),
            "attributes": {
                "brand": brand,
                "model": car_data.get("model"),
                "year": car_data.get("vehicleModelDate"),
                "mileage": str(mileage) if mileage is not None else None,
                "version": car_data.get("vehicleConfiguration"),
                "body_type": car_data.get("bodyType"),
                "color": car_data.get("color"),
                "transmission": car_data.get("vehicleTransmission"),
                "fuel_type": ((car_data.get("vehicleEngine") or {}).get("fuelType")),
                "vin": car_data.get("vehicleIdentificationNumber"),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_car_ld_json(html: str) -> dict:
        for match in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            try:
                payload = json.loads(match.group(1))
            except Exception:
                continue
            if isinstance(payload, dict):
                for node in payload.get("@graph", []):
                    if isinstance(node, dict) and node.get("@type") == "Car":
                        return node
        return {}

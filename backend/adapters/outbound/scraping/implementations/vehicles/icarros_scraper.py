"""
iCarros Scraper
Scrapes vehicle listings from iCarros
"""
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class ICarrosScraper(HTTPScraper):
    """Scraper for iCarros vehicle listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="icarros",
                display_name="iCarros",
                description="Scraper de veículos do iCarros",
                category=ScrapingCategory.VEHICLES,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.icarros.com.br",
            endpoint="/comprar/brasil",
            enabled=False,
            rate_limit_delay=2.0,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping iCarros from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/comprar/'][href*='/d']")
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
                    continue

            self.logger.info(f"Scraped {len(items)} items from iCarros")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping iCarros: {e}")
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
        vehicle_data = self._extract_vehicle_ld_json(html)
        if not vehicle_data:
            return None

        soup = self.parse_html(html)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        city, state = self._extract_city_state(url, page_text)
        description = self.extract_attr(soup, "meta[name='description']", "content") or page_text[:1200]

        images = []
        for image in vehicle_data.get("image") or []:
            if isinstance(image, dict):
                value = image.get("contentUrl")
            else:
                value = image
            if value and value not in images:
                images.append(value)

        offers = vehicle_data.get("offers") or {}
        mileage = (vehicle_data.get("mileageFromOdometer") or {}).get("value")
        brand = ((vehicle_data.get("brand") or {}).get("name") if isinstance(vehicle_data.get("brand"), dict) else vehicle_data.get("brand"))

        scraped_data = {
            "title": vehicle_data.get("name"),
            "description": description,
            "price": self.parse_price(str(offers.get("price"))) if offers.get("price") is not None else None,
            "currency": offers.get("priceCurrency") or "BRL",
            "city": city,
            "state": state,
            "images": images,
            "attributes": {
                "brand": brand,
                "model": vehicle_data.get("model"),
                "year": vehicle_data.get("vehicleModelDate"),
                "mileage": str(mileage) if mileage is not None else None,
                "fuel_type": vehicle_data.get("fuelType"),
                "transmission": vehicle_data.get("vehicleTransmission"),
                "body_type": vehicle_data.get("bodyType"),
                "color": vehicle_data.get("color"),
                "item_condition": vehicle_data.get("itemCondition"),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_vehicle_ld_json(html: str) -> dict:
        for match in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            try:
                payload = json.loads(match.group(1))
            except Exception:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "Vehicle":
                return payload
        return {}

    @staticmethod
    def _extract_city_state(url: str, page_text: str) -> tuple[Optional[str], Optional[str]]:
        path_match = re.search(r"/comprar/([a-z\-]+)-([a-z]{2})/", url)
        if path_match:
            city = path_match.group(1).replace("-", " ").title()
            state = path_match.group(2).upper()
            return city, state

        text_match = re.search(r"([A-ZÀ-Úa-zà-ú\s]+)\s*-\s*([A-Z]{2})", page_text)
        if text_match:
            return text_match.group(1).strip().title(), text_match.group(2).upper()
        return None, None

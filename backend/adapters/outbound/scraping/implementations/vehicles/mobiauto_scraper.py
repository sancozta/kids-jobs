"""
MobiAuto Scraper
Scrapes vehicle listings from MobiAuto
"""
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class MobiAutoScraper(HTTPScraper):
    """Scraper for MobiAuto vehicle listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="mobiauto",
                display_name="MobiAuto",
                description="Scraper de veículos do MobiAuto",
                category=ScrapingCategory.VEHICLES,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.mobiauto.com.br",
            endpoint="/comprar/carros",
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
            self.logger.info(f"Scraping MobiAuto from: {url}")
            response = self.fetch_page(url)
            if not response:
                return items
            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/comprar/'][href*='/detalhes/']")
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
            self.logger.info(f"Scraped {len(items)} items from MobiAuto")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping MobiAuto: {e}")
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = (url or "").strip().split("?")[0]
        if not normalized_url:
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None
        return self._parse_detail_page(normalized_url, response.text)

    def _parse_detail_page(self, url: str, html: str) -> Optional[ScrapedItem]:
        next_data = self._extract_next_data(html)
        page_props = ((next_data.get("props") or {}).get("pageProps") or {})
        deal = page_props.get("deal") or {}
        if not deal:
            return None

        images = [image.get("imageSrc") for image in (page_props.get("images") or []) if image.get("imageSrc")]
        if not images:
            images = [image.get("src") for image in (deal.get("images") or []) if image.get("src")]

        city = self._normalize_title_case(deal.get("dealerCity"))
        state = (deal.get("dealerState") or "").upper() or None
        description = (deal.get("comments") or "").strip() or None

        scraped_data = {
            "title": self._build_title(deal),
            "description": description,
            "price": deal.get("price"),
            "currency": "BRL",
            "city": city,
            "state": state,
            "street": self._normalize_title_case(deal.get("dealerAddress")),
            "images": images,
            "attributes": {
                "brand": deal.get("makeName"),
                "model": deal.get("modelName"),
                "version": deal.get("trimName"),
                "year": str(deal.get("modelYear")) if deal.get("modelYear") else None,
                "production_year": str(deal.get("productionYear")) if deal.get("productionYear") else None,
                "mileage": str(deal.get("km")) if deal.get("km") is not None else None,
                "fuel_type": deal.get("fuelName"),
                "transmission": deal.get("transmissionName"),
                "body_type": deal.get("bodystyleName"),
                "color": deal.get("colorName"),
                "doors": str(deal.get("doors")) if deal.get("doors") is not None else None,
                "dealer_name": deal.get("dealerName"),
                "dealer_type": deal.get("dealerType"),
                "dealer_phone": deal.get("dealerPhone"),
            },
        }

        dealer_location = (deal.get("dealerLocation") or "").split(",")
        if len(dealer_location) == 2:
            try:
                scraped_data["location"] = {
                    "latitude": float(dealer_location[0]),
                    "longitude": float(dealer_location[1]),
                }
            except ValueError:
                pass

        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_next_data(html: str) -> dict:
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except Exception:
            return {}

    @staticmethod
    def _build_title(deal: dict) -> str:
        parts = [
            deal.get("makeName"),
            deal.get("modelName"),
            str(deal.get("modelYear")) if deal.get("modelYear") else None,
            deal.get("trimName"),
        ]
        return " ".join(part.strip() for part in parts if part).strip() or "Veículo MobiAuto"

    @staticmethod
    def _normalize_title_case(value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip()
        if not normalized:
            return None
        return normalized.title()

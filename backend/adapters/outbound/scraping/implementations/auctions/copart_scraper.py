"""
Copart Scraper
Scrapes vehicle auction listings from Copart Brasil
"""
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class CopartScraper(HTTPScraper):
    """Scraper for Copart vehicle auction listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="copart",
                display_name="Copart Brasil",
                description="Scraper de leilões de veículos da Copart",
                category=ScrapingCategory.AUCTIONS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.copart.com.br",
            endpoint="/search/compre_agora/?displayStr=Compre%20Agora&from=%2FvehicleFinder",
            enabled=False,
            rate_limit_delay=3.0,
            max_items_per_run=50,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3200,
                "playwright_persistent_session": True,
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Copart from: {url}")
            response = self.fetch_page(url)
            if not response:
                return items
            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/lot/']")
            seen_urls: set[str] = set()
            for listing in listings:
                href = listing.get("href", "").strip()
                listing_url = self._normalize_listing_url(urljoin(self.config.base_url, href))
                if not listing_url or listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                idx = len(items)
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self._parse_listing(listing)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
            self.logger.info(f"Scraped {len(items)} items from Copart")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Copart: {e}")
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        try:
            url = self._normalize_listing_url(urljoin(self.config.base_url, listing.get("href", "")))
            if not url:
                return None

            raw_text = " ".join(listing.get_text(" ", strip=True).split())
            context_text = " ".join(listing.parent.get_text(" ", strip=True).split()) if listing.parent else raw_text
            lot_id = self._extract_lot_id(url)

            price_text = next((match for match in re.findall(r"R\\$\\s?[\\d\\.]+,\\d{2}", context_text) if match), None)
            price = self.parse_price(price_text)

            title = raw_text[:140] if raw_text else None
            if not title:
                lot_match = re.search(r"/lot/([^/?#]+)", url)
                lot_id = lot_match.group(1) if lot_match else "desconhecido"
                title = f"Lote Copart {lot_id}"

            image_elem = listing.parent.select_one("img[src]") if listing.parent else None
            image_url = image_elem.get("src", "").strip() if image_elem else ""
            images = [image_url] if image_url else []

            location = None
            location_match = re.search(r"([A-Za-zÀ-ÿ\\s]+)\\s*-\\s*([A-Z]{2})", context_text)
            if location_match:
                location = f"{location_match.group(1).strip()} - {location_match.group(2).strip()}"

            scraped_data = {
                "title": title,
                "description": context_text[:500] if context_text else None,
                "price": price,
                "currency": "BRL",
                "images": images,
                "location": {"raw": location},
                "attributes": {
                    "listing_type": "direct_sale",
                    "lot_number": lot_id,
                    "auction_code": lot_id,
                    "asset_type": "veiculo",
                    "auctioneer": "Copart Brasil",
                },
            }
            return self.build_scraped_item(
                url=url,
                scraped_data=scraped_data,
            )
        except Exception as e:
            self.logger.error(f"Error parsing listing: {e}")
            return None

    @staticmethod
    def _normalize_listing_url(value: str) -> str:
        normalized = (value or "").strip().split("?", 1)[0].rstrip("/")
        lot_id = CopartScraper._extract_lot_id(normalized)
        if not lot_id:
            return ""
        return f"https://www.copart.com.br/lot/{lot_id}"

    @staticmethod
    def _extract_lot_id(value: str) -> Optional[str]:
        match = re.search(r"/lot/(\d+)", (value or "").strip())
        return match.group(1) if match else None

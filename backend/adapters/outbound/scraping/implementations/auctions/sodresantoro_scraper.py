"""
Sodré Santoro Scraper
Scrapes auction listings from Sodré Santoro Leilões.
"""
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory, ScrapingStrategy


class SodreSantoroScraper(HTTPScraper):
    """Scraper for Sodré Santoro auction listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="sodresantoro",
                display_name="Sodré Santoro",
                description="Scraper de leilões do Sodré Santoro",
                category=ScrapingCategory.AUCTIONS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.sodresantoro.com.br",
            endpoint="/imoveis/lotes?lot_category=casa",
            enabled=True,
            rate_limit_delay=2.0,
            max_items_per_run=50,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3000,
                "playwright_persistent_session": True,
                "playwright_headful_fallback": True,
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Sodré Santoro from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='leilao.sodresantoro.com.br/leilao/'][href*='/lote/']")

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

            self.logger.info(f"Scraped {len(items)} items from Sodré Santoro")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Sodré Santoro: {e}")
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        try:
            url = self._normalize_listing_url(listing.get("href", ""))
            if not url:
                return None

            raw_text = " ".join(listing.get_text(" ", strip=True).split())
            title = self._extract_title(raw_text, listing)

            price_text = next(
                (
                    match
                    for match in re.findall(r"R\$\s?[\d\.]+(?:,\d{2})?", raw_text)
                ),
                None,
            )
            if not price_text:
                price_match = re.search(r"Lance\s+(?:inicial|atual)\s+\(R\$\)\s*([\d\.]+(?:,\d{2})?)", raw_text, re.IGNORECASE)
                price_text = price_match.group(1) if price_match else None
            price = self.parse_price(price_text)
            auction_datetime = self._extract_auction_datetime(raw_text)
            location = self._extract_location(raw_text)
            image_elem = listing.select_one("img[src]")
            image_url = image_elem.get("src", "").strip() if image_elem else ""
            asset_type = self._extract_asset_type(raw_text)
            auction_id, lot_number, auction_code = self._extract_auction_identifiers(raw_text, url)
            description = raw_text

            scraped_data = {
                "title": title,
                "description": description,
                "price": price,
                "currency": "BRL",
                "images": [image_url] if image_url else [],
                "location": {"raw": location},
                "attributes": {
                    "auction_id": auction_id,
                    "lot_number": lot_number,
                    "auction_code": auction_code,
                    "auction_date": auction_datetime,
                    "auction_start_at": auction_datetime,
                    "listing_type": "auction",
                    "auction_status": "aberto",
                    "asset_type": asset_type,
                    "auctioneer": "Sodré Santoro",
                },
            }

            if not self._is_target_property(title, asset_type):
                return None

            return self.build_scraped_item(
                url=url,
                scraped_data=scraped_data,
            )
        except Exception as e:
            self.logger.error(f"Error parsing listing: {e}")
            return None

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized = self._normalize_listing_url(url)
        if not normalized:
            return None

        response = self.fetch_page(normalized)
        if not response:
            return None

        soup = self.parse_html(response.text)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        title = (
            self.extract_attr(soup, "meta[property='og:title']", "content")
            or self.extract_text(soup, "h1")
            or self._extract_title(page_text, soup)
        )
        title = re.sub(r"\s*\|\s*Sodre Santoro.*$", "", title or "", flags=re.IGNORECASE).strip()
        price = self.parse_price(next((match for match in re.findall(r"R\$\s?[\d\.]+,\d{2}", page_text)), None))
        image = self.extract_attr(soup, "meta[property='og:image']", "content")
        description = self.extract_text(soup, "body") or page_text

        asset_type = self._extract_asset_type(page_text)
        if not self._is_target_property(title, asset_type):
            return None

        auction_id, lot_number, auction_code = self._extract_auction_identifiers(page_text, normalized)
        auction_datetime = self._extract_auction_datetime(page_text)

        return self.build_scraped_item(
            url=normalized,
            scraped_data={
                "title": title,
                "description": description[:4000] if description else None,
                "price": price,
                "currency": "BRL",
                "images": [image] if image else [],
                "location": {"raw": self._extract_location(page_text)},
                "attributes": {
                    "auction_id": auction_id,
                    "lot_number": lot_number,
                    "auction_code": auction_code,
                    "listing_type": "auction",
                    "auction_date": auction_datetime,
                    "auction_start_at": auction_datetime,
                    "auction_status": "aberto",
                    "asset_type": asset_type,
                    "auctioneer": "Sodré Santoro",
                },
            },
        )

    @staticmethod
    def _normalize_listing_url(value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return ""
        normalized = normalized.split("?", 1)[0].rstrip("/")
        if "/leilao/" not in normalized or "/lote/" not in normalized:
            return ""
        return normalized

    @staticmethod
    def _extract_title(raw_text: str, listing) -> str:
        image_elem = listing.select_one("img[alt]") if hasattr(listing, "select_one") else None
        alt_text = image_elem.get("alt", "").strip() if image_elem else ""
        if alt_text.lower().startswith("imagem 1 do "):
            return alt_text[11:].strip()

        match = re.search(
            r"Leil[aã]o\s+\d+\s*-\s*\d+\s+\d+\s+(.*?)\s+(?:[A-ZÁ-Ú].*?\d{2}/\d{2}/\d{2}|\d{2}/\d{2}/\d{2})",
            raw_text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return raw_text[:180].strip()

    @staticmethod
    def _extract_auction_datetime(raw_text: str) -> Optional[str]:
        match = re.search(r"(\d{2}/\d{2}/(?:\d{2}|\d{4})\s+\d{2}:\d{2})", raw_text)
        return match.group(1) if match else None

    @staticmethod
    def _extract_auction_identifiers(raw_text: str, url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        text_match = re.search(r"Leil[aã]o\s+(\d+)\s*-\s*(\d+)\s+(\d+)", raw_text, re.IGNORECASE)
        if text_match:
            return text_match.group(1), text_match.group(2), text_match.group(3)

        url_match = re.search(r"/leilao/(\d+)/lote/(\d+)", url)
        if not url_match:
            return None, None, None
        return url_match.group(1), None, url_match.group(2)

    @staticmethod
    def _extract_location(raw_text: str) -> Optional[str]:
        matches = re.findall(r"([A-Za-zÀ-ÿ\s]+)\s*/\s*([A-Z]{2})", raw_text)
        if not matches:
            return None
        city, state = matches[-1]
        return f"{city.strip()} - {state.strip()}"

    @staticmethod
    def _extract_asset_type(raw_text: str) -> Optional[str]:
        match = re.search(r"\b(casa|terreno|apartamento|galp[aã]o|im[oó]vel|loja|sala|rural)\b", raw_text, re.IGNORECASE)
        return match.group(1).lower() if match else None

    @staticmethod
    def _is_target_property(title: Optional[str], asset_type: Optional[str]) -> bool:
        haystack = " ".join(part for part in [title or "", asset_type or ""]).lower()
        include_tokens = (
            "casa",
            "sobrado",
            "apartamento",
            "condom",
            "residencial",
            "terreno",
            "lote",
            "imovel",
            "imóvel",
            "chacara",
            "chácara",
            "fazenda",
            "sitio",
            "sítio",
            "rural",
        )
        exclude_tokens = ("veiculo", "carro", "moto", "caminh", "sala", "consultorio", "consultório", "galp", "loja")
        return any(token in haystack for token in include_tokens) and not any(token in haystack for token in exclude_tokens)

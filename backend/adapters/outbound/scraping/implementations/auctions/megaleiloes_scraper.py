"""
Mega Leilões Scraper
Scrapes auction listings from Mega Leilões
"""
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class MegaLeiloesScraper(HTTPScraper):
    """Scraper for Mega Leilões auction listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="megaleiloes",
                display_name="Mega Leilões",
                description="Scraper de leilões do Mega Leilões",
                category=ScrapingCategory.AUCTIONS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.megaleiloes.com.br",
            endpoint="/",
            enabled=True,
            rate_limit_delay=2.0,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Mega Leilões from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/imoveis/']")
            seen_urls: set[str] = set()

            for listing in listings:
                href = listing.get("href", "").strip()
                listing_url = urljoin(self.config.base_url, href).split("?")[0]
                if not listing_url or listing_url in seen_urls:
                    continue
                if not self._is_candidate_url(listing_url):
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

            self.logger.info(f"Scraped {len(items)} items from Mega Leilões")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Mega Leilões: {e}")
            return items

    @staticmethod
    def _is_candidate_url(url: str) -> bool:
        if "/veiculos/" in url:
            return False
        if re.search(r"-(?:j|x)\d{5,}$", url, re.IGNORECASE):
            return True
        if "/imoveis/" in url and url.count("/") >= 6:
            return True
        return False

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = (url or "").strip().split("?", 1)[0].rstrip("/")
        if not normalized_url:
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None
        return self._parse_detail_page(normalized_url, response.text)

    def _parse_detail_page(self, url: str, html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(html)
        page_text = " ".join(soup.get_text(" ", strip=True).split())

        title = (
            self.extract_text(soup, "title")
            or self.extract_attr(soup, "meta[property='og:title']", "content")
            or self.extract_attr(soup, "meta[name='description']", "content")
            or "Item Mega Leilões"
        )
        title = re.sub(r"\s*\|\s*Mega Leilões$", "", title, flags=re.IGNORECASE).strip()

        description = self.extract_text(soup, "#tab-description .content")
        if not description:
            description = self.extract_text(soup, ".page-detail .description .content")

        images = []
        for node in soup.select("[data-mfp-src], meta[property='og:image'][content]"):
            src = node.get("data-mfp-src") or node.get("content")
            if src:
                normalized = urljoin(self.config.base_url, src.strip())
                if normalized not in images:
                    images.append(normalized)

        price_text = next((match for match in re.findall(r"R\$\s?[\d\.]+,\d{2}", page_text)), None)
        price = self.parse_price(price_text)

        first_praca = re.search(r"1ª Praça:\s*(\d{2}/\d{2}/\d{4}) às (\d{2}:\d{2}).*?R\$\s?([\d\.]+,\d{2})", page_text)
        second_praca = re.search(r"2ª Praça:\s*(\d{2}/\d{2}/\d{4}) às (\d{2}:\d{2}).*?R\$\s?([\d\.]+,\d{2})", page_text)
        code_match = re.search(r"-(?:j|x)(\d{5,})$", url, re.IGNORECASE)
        parts = [segment for segment in url.split("/") if segment]
        state_code = parts[-3].upper() if len(parts) >= 3 else None
        city_name = parts[-2].replace("-", " ").title() if len(parts) >= 2 else None

        asset_type = self._extract_asset_type(title)
        first_praca_value = self.parse_price(first_praca.group(3)) if first_praca else None
        second_praca_value = self.parse_price(second_praca.group(3)) if second_praca else None
        lot_code = code_match.group(1) if code_match else None
        scraped_data = {
            "title": title,
            "description": description or None,
            "price": price,
            "currency": "BRL",
            "images": images,
            "state": state_code,
            "city": city_name,
            "attributes": {
                "listing_type": "auction",
                "auction_code": lot_code,
                "lot_number": lot_code,
                "auction_date": first_praca.group(1) if first_praca else None,
                "auction_status": "aberto" if "aberto para lances" in page_text.lower() else None,
                "auction_start_at": f"{first_praca.group(1)} {first_praca.group(2)}" if first_praca else None,
                "auction_end_at": f"{second_praca.group(1)} {second_praca.group(2)}" if second_praca else None,
                "minimum_bid": second_praca_value or first_praca_value,
                "appraisal_value": first_praca_value,
                "discount_pct": self.compute_discount_pct(first_praca_value, second_praca_value),
                "asset_type": asset_type,
                "auctioneer": "Mega Leilões",
            },
        }
        if not self._is_target_property(title, asset_type):
            return None

        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_asset_type(title: str) -> Optional[str]:
        match = re.search(r"\b(casa|apartamento|imovel|imóvel|terreno|rural|comercial|galp[aã]o|ve[ií]culo)\b", title, re.IGNORECASE)
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
            "imovel",
            "imóvel",
            "chacara",
            "chácara",
            "fazenda",
            "sitio",
            "sítio",
            "rural",
        )
        exclude_tokens = ("veiculo", "veículo", "galp", "loja", "sala", "consult", "comercial")
        return any(token in haystack for token in include_tokens) and not any(token in haystack for token in exclude_tokens)

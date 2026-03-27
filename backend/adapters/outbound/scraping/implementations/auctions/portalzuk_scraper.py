"""
Portal Zuk Scraper
Scrapes auction/property listings from Portal Zuk.
"""
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class PortalZukScraper(HTTPScraper):
    """Scraper for Portal Zuk auction/property listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="portalzuk",
                display_name="Portal Zuk",
                description="Scraper de leilões e imóveis do Portal Zuk",
                category=ScrapingCategory.AUCTIONS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.portalzuk.com.br",
            endpoint="/leilao-de-imoveis/tl/proximos-leiloes",
            enabled=True,
            rate_limit_delay=2.5,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Portal Zuk from: {url}")
            response = self.fetch_page(url)
            if not response:
                return items
            soup = self.parse_html(response.text)
            listing_urls = self._extract_listing_urls(soup)
            for idx, listing_url in enumerate(listing_urls):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self.scrape_url(listing_url)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
            self.logger.info(f"Scraped {len(items)} items from Portal Zuk")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Portal Zuk: {e}")
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = self._normalize_listing_url(url)
        if not normalized_url:
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None

        return self._parse_detail_page(normalized_url, response.text)

    def _extract_listing_urls(self, soup) -> list[str]:
        seen: set[str] = set()
        listing_urls: list[str] = []
        for anchor in soup.select("a[href*='/imovel/']"):
            href = anchor.get("href", "").strip()
            normalized = self._normalize_listing_url(urljoin(self.config.base_url, href))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            listing_urls.append(normalized)
        return listing_urls

    def _normalize_listing_url(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return ""

        normalized = urljoin(self.config.base_url, normalized)
        parsed = urlparse(normalized)
        if "/imovel/" not in parsed.path:
            return ""
        path = parsed.path.rstrip("/")
        if not re.search(r"/\d{4,}-\d{4,}$", path):
            return ""
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _parse_detail_page(self, url: str, html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(html)

        title = (
            self.extract_attr(soup, "meta[property='og:title']", "content")
            or self.extract_text(soup, "h1")
            or "Imóvel Portal Zuk"
        )
        title = re.sub(r"\s*\|\s*Zuk$", "", title, flags=re.IGNORECASE).strip()

        description_parts = []
        for heading in ("Descrição do imóvel", "Observações", "Visitação"):
            section = self._extract_section_after_heading(soup, heading)
            if section:
                description_parts.append(section)
        description = "\n\n".join(part for part in description_parts if part)

        images = []
        for image in soup.select(".property-gallery-image img[src], meta[property='og:image'][content]"):
            src = image.get("src") or image.get("content")
            if src:
                normalized = urljoin(self.config.base_url, src.strip())
                if normalized not in images:
                    images.append(normalized)

        page_text = soup.get_text(" ", strip=True)
        price_context = self._extract_price_context(soup, page_text)
        price = price_context["primary_price"]

        state_code, city_name, street_name = self._extract_location_from_url(url)
        asset_type = self._extract_asset_type(title)
        listing_type = "direct_sale" if "proposta" in page_text.lower() else "auction"
        auction_status = "aberto" if ("aberto" in page_text.lower() or "proposta" in page_text.lower()) else None
        auction_id, lot_number = self._extract_identifiers_from_url(url)
        auction_code = "-".join(part for part in [auction_id, lot_number] if part) or None
        date_matches = re.findall(r"(\d{2}/\d{2}/\d{4})\s+às\s+(\d{2}:\d{2})", page_text)
        first_date_text = f"{date_matches[0][0]} {date_matches[0][1]}" if date_matches else None
        second_date_text = f"{date_matches[1][0]} {date_matches[1][1]}" if len(date_matches) > 1 else None
        appraisal_value = price_context["first_auction_value"]
        minimum_bid = price_context["minimum_bid"] or price_context["second_auction_value"]

        scraped_data = {
            "title": title,
            "description": description or None,
            "price": price,
            "currency": "BRL",
            "state": state_code,
            "city": city_name,
            "street": street_name,
            "images": images,
            "attributes": {
                "listing_type": listing_type,
                "auction_id": auction_id,
                "lot_number": lot_number,
                "auction_status": auction_status,
                "auction_code": auction_code,
                "auction_date": date_matches[0][0] if date_matches else None,
                "auction_start_at": first_date_text,
                "auction_end_at": second_date_text,
                "asset_type": asset_type,
                "appraisal_value": appraisal_value,
                "minimum_bid": minimum_bid,
                "discount_pct": self.compute_discount_pct(appraisal_value, price),
                "auctioneer": "Portal Zuk",
            },
        }
        if not self._is_target_property(title):
            return None

        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_section_after_heading(self, soup, heading_text: str) -> Optional[str]:
        for heading in soup.select(".property-info-title"):
            if heading.get_text(" ", strip=True).lower() != heading_text.lower():
                continue
            container = heading.find_parent(class_="property-info")
            if not container:
                continue
            text = self.extract_text(container, ".property-info-text")
            if text:
                return text
        return None

    def _extract_price_context(self, soup, page_text: str) -> dict[str, Optional[float]]:
        price_candidates: list[tuple[int, float]] = []
        sale_price: Optional[float] = None
        first_auction_value: Optional[float] = None
        second_auction_value: Optional[float] = None

        for price_item in soup.select(".card-property-price"):
            label_element = price_item.select_one(".card-property-price-label")
            value_element = price_item.select_one(".card-property-price-value")
            label = (label_element.get_text(" ", strip=True) if label_element else "").lower()
            value = value_element.get_text(" ", strip=True) if value_element else ""
            parsed = self.parse_price(value)
            if parsed is None:
                continue

            priority = 99
            if "valor" in label:
                priority = 0
                sale_price = parsed
            elif "1º leilão" in label or "1o leilao" in label:
                priority = 1
                first_auction_value = parsed
            elif "2º leilão" in label or "2o leilao" in label:
                priority = 2
                second_auction_value = parsed

            price_candidates.append((priority, parsed))

        minimum_bid_text = self.extract_text(soup, ".form-help") or self.extract_text(soup, ".box-action-bid-value")
        minimum_bid_match = re.search(r"R\$\s?[\d\.]+,\d{2}", minimum_bid_text or "")
        minimum_bid = self.parse_price(minimum_bid_match.group(0)) if minimum_bid_match else None

        primary_price: Optional[float] = None
        if price_candidates:
            price_candidates.sort(key=lambda item: item[0])
            primary_price = price_candidates[0][1]
        else:
            primary_price = self.parse_price(page_text)

        return {
            "primary_price": primary_price,
            "sale_price": sale_price,
            "first_auction_value": first_auction_value,
            "second_auction_value": second_auction_value,
            "minimum_bid": minimum_bid,
        }

    @staticmethod
    def _extract_identifiers_from_url(url: str) -> tuple[Optional[str], Optional[str]]:
        match = re.search(r"/(\d{4,})-(\d{4,})$", url)
        if not match:
            return None, None
        return match.group(1), match.group(2)

    @staticmethod
    def _extract_asset_type(title: str) -> Optional[str]:
        match = re.search(
            r"\b(casa|apartamento|imovel|imóvel|terreno|chacara|chácara|fazenda|sitio|sítio|rural|sobrado|predio|prédio)\b",
            title,
            re.IGNORECASE,
        )
        return match.group(1).lower() if match else None

    @staticmethod
    def _is_target_property(title: Optional[str]) -> bool:
        haystack = (title or "").lower()
        include_tokens = (
            "casa",
            "sobrado",
            "apartamento",
            "condom",
            "residencial",
            "terreno",
            "imóvel",
            "imovel",
            "chácara",
            "chacara",
            "fazenda",
            "sítio",
            "sitio",
            "rural",
        )
        exclude_tokens = ("prédio comercial", "predio comercial", "sala", "consultório", "consultorio", "galpão", "galpao", "loja")
        return any(token in haystack for token in include_tokens) and not any(token in haystack for token in exclude_tokens)

    @staticmethod
    def _extract_location_from_url(url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 6:
            return None, None, None
        state_code = parts[1].upper()
        city_name = parts[2].replace("-", " ").title()
        street_name = parts[4].replace("-", " ").replace("_", " ").strip()
        return state_code, city_name, street_name or None

"""
SuperBid Scraper
Scrapes auction listings from SuperBid
"""
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class SuperBidScraper(HTTPScraper):
    """Scraper for SuperBid auction listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="superbid",
                display_name="SuperBid",
                description="Scraper de leilões do SuperBid",
                category=ScrapingCategory.AUCTIONS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.superbid.net",
            endpoint="/categorias/imoveis?searchType=opened",
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
            self.logger.info(f"Scraping SuperBid from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select("a[href*='/oferta/'], a[href*='exchange.superbid.net/oferta/']")
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

            self.logger.info(f"Scraped {len(items)} items from SuperBid")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping SuperBid: {e}")
            return items

    @staticmethod
    def _is_candidate_url(url: str) -> bool:
        return "/oferta/" in url

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = (url or "").strip().split("?", 1)[0].rstrip("/")
        if not self._is_candidate_url(normalized_url):
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None

        return self._parse_detail_page(normalized_url, response.text)

    def _parse_detail_page(self, url: str, html: str) -> Optional[ScrapedItem]:
        next_data = self._extract_next_data(html)
        offer = (((next_data or {}).get("props") or {}).get("pageProps") or {}).get("offerDetails", {}).get("offers", [])
        event = (((next_data or {}).get("props") or {}).get("pageProps") or {}).get("eventDetails", {}).get("events", [])
        if not offer:
            return None

        offer_data = offer[0]
        event_data = event[0] if event else {}
        product = offer_data.get("product") or {}
        auction = offer_data.get("auction") or {}
        seller = offer_data.get("seller") or {}
        store = offer_data.get("store") or {}
        location = product.get("location") or {}
        address = auction.get("address") or event_data.get("address") or {}

        images = []
        for image in product.get("galleryJson") or []:
            link = (image or {}).get("link")
            if link and link not in images:
                images.append(link)
        if not images:
            for image in event_data.get("gallery") or []:
                link = (image or {}).get("link")
                if link and link not in images:
                    images.append(link)
        if not images:
            og_image = self.extract_attr(self.parse_html(html), "meta[property='og:image']", "content")
            if og_image:
                images.append(og_image)

        description = product.get("detailedDescription")
        if not description:
            description = ((offer_data.get("offerDescription") or {}).get("offerDescription"))

        title = product.get("shortDesc") or self._title_from_url(url)

        street_parts = [
            address.get("streetType"),
            address.get("street"),
            address.get("number"),
        ]
        street = " ".join(str(part).strip() for part in street_parts if part).strip() or None

        title_city, title_state = self._extract_city_state_from_title(title)
        parsed_location_city, parsed_location_state = self._split_city_state(location.get("city"))
        raw_city = title_city or parsed_location_city or location.get("city") or address.get("city")
        state = title_state or parsed_location_state or address.get("stateCode") or self._normalize_state(location.get("state"))

        asset_type = ((product.get("productType") or {}).get("description"))
        auction_id = str(auction.get("id")).strip() if auction.get("id") is not None else None
        lot_number = str(offer_data.get("lotNumber")).strip() if offer_data.get("lotNumber") is not None else None
        auction_code = "-".join(part for part in [auction_id, lot_number] if part) or None
        scraped_data = {
            "title": title,
            "description": description,
            "price": offer_data.get("price"),
            "currency": (auction.get("currencyIso") or "BRL").upper(),
            "city": raw_city,
            "state": state,
            "street": street,
            "images": images,
            "attributes": {
                "listing_type": "auction",
                "auction_id": auction_id,
                "lot_number": lot_number,
                "auction_code": auction_code,
                "auction_date": auction.get("beginDate") or offer_data.get("endDateTime") or auction.get("endDate"),
                "auction_status": self._normalize_status((offer_data.get("offerStatus") or {}).get("desc")),
                "auction_start_at": auction.get("beginDate"),
                "auction_end_at": offer_data.get("endDateTime") or auction.get("endDate"),
                "current_bid": offer_data.get("price"),
                "asset_type": asset_type,
                "auctioneer": store.get("name") or seller.get("name"),
            },
        }

        location_geo = (location.get("locationGeo") or {})
        if location_geo.get("lat") is not None and location_geo.get("lon") is not None:
            scraped_data["location"] = {
                "latitude": location_geo.get("lat"),
                "longitude": location_geo.get("lon"),
            }

        if not self._is_target_property(title, asset_type):
            return None

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
    def _normalize_status(value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip().lower()
        if not normalized:
            return None
        if "abert" in normalized or "andamento" in normalized:
            return "aberto"
        if "encerr" in normalized or "finaliz" in normalized:
            return "encerrado"
        if "suspens" in normalized:
            return "suspenso"
        return normalized

    @staticmethod
    def _title_from_url(url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"-\d+$", "", slug)
        return slug.replace("-", " ").strip().title() or "Oferta Superbid"

    @staticmethod
    def _normalize_state(value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip()
        if not normalized:
            return None

        uf_map = {
            "acre": "AC",
            "alagoas": "AL",
            "amapa": "AP",
            "amazonas": "AM",
            "bahia": "BA",
            "ceara": "CE",
            "distrito federal": "DF",
            "espirito santo": "ES",
            "goias": "GO",
            "maranhao": "MA",
            "mato grosso": "MT",
            "mato grosso do sul": "MS",
            "minas gerais": "MG",
            "para": "PA",
            "paraiba": "PB",
            "parana": "PR",
            "pernambuco": "PE",
            "piaui": "PI",
            "rio de janeiro": "RJ",
            "rio grande do norte": "RN",
            "rio grande do sul": "RS",
            "rondonia": "RO",
            "roraima": "RR",
            "santa catarina": "SC",
            "sao paulo": "SP",
            "sergipe": "SE",
            "tocantins": "TO",
        }
        collapsed = re.sub(r"[^a-z ]", "", normalized.lower())
        if len(normalized) == 2 and normalized.isalpha():
            return normalized.upper()
        return uf_map.get(collapsed)

    @staticmethod
    def _extract_city_state_from_title(title: str) -> tuple[Optional[str], Optional[str]]:
        normalized = (title or "").strip()
        if not normalized:
            return None, None

        patterns = [
            r"([A-ZÀ-Üa-zà-ü\s'\.-]+)\s*/\s*([A-Z]{2})(?:\s|\(|$)",
            r"([A-ZÀ-Üa-zà-ü\s'\.-]+)\s*-\s*([A-Z]{2})(?:\s|\(|$)",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, normalized))
            if not matches:
                continue
            city = matches[-1].group(1).strip(" -/,")
            state = matches[-1].group(2).upper()
            return city, state
        return None, None

    @staticmethod
    def _split_city_state(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        normalized = (value or "").strip()
        if not normalized:
            return None, None

        match = re.match(r"(.+?)\s*[-/]\s*([A-Z]{2})$", normalized)
        if not match:
            return normalized, None

        city = match.group(1).strip()
        state = match.group(2).upper()
        return city, state

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
            "prédio",
            "predio",
        )
        exclude_tokens = ("veiculo", "veículo", "sala", "consult", "galp", "loja")
        return any(token in haystack for token in include_tokens) and not any(token in haystack for token in exclude_tokens)

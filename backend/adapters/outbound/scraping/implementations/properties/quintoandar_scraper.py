"""
QuintoAndar Scraper
Scrapes sale house listings from QuintoAndar using list URLs from HTML and detail data from __NEXT_DATA__.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any, Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class QuintoAndarScraper(HTTPScraper):
    """Scraper for QuintoAndar property listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="quintoandar",
                display_name="QuintoAndar",
                description="Scraper de casas a venda do QuintoAndar em Porto Alegre",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.quintoandar.com.br",
            endpoint="/comprar/imovel/porto-alegre-rs-brasil/casa",
            enabled=True,
            rate_limit_delay=2.5,
            max_items_per_run=30,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return items

        seen: set[str] = set()
        for url in self._extract_listing_urls(response.text):
            if url in seen:
                continue
            seen.add(url)
            item = self.scrape_url(url)
            if item:
                items.append(item)
            if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                break
        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        response = self.fetch_page(url)
        if not response:
            return None

        page_text = self.parse_html(response.text).get_text("\n", strip=True)
        house_info = self._extract_house_info(response.text)
        if not house_info:
            return None

        address = house_info.get("address") or {}
        city = self._normalize_text(address.get("city"))
        state = self._normalize_text(address.get("stateAcronym"))
        neighborhood = self._normalize_text(address.get("neighborhood"))
        street = self._build_street(address)
        title = self._build_title(house_info, neighborhood, city)
        description = self._build_description(house_info, page_text=page_text)
        price = self._to_float(house_info.get("salePrice"))
        total_area = self._to_float(house_info.get("area"))
        bedrooms = self._to_int(house_info.get("bedrooms"))
        bathrooms = self._to_int(house_info.get("bathrooms"))
        parking_spaces = self._to_int(house_info.get("parkingSpaces"))
        amenities = self._extract_amenities(house_info.get("amenities"))
        images = self._extract_images(house_info.get("photos"))

        location = None
        lat = address.get("lat")
        lng = address.get("lng")
        if lat is not None and lng is not None:
            try:
                location = {"latitude": float(lat), "longitude": float(lng)}
            except (TypeError, ValueError):
                location = None

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "city": city,
            "state": state,
            "zip_code": self._normalize_text(address.get("zipCode")),
            "street": street,
            "location": location,
            "images": images,
            "attributes": {
                "listing_type": "sale",
                "property_type": self._normalize_text(house_info.get("type"), fallback="casa"),
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "parking_spots": parking_spaces,
                "total_area_m2": total_area,
                "iptu": self._to_float(house_info.get("iptu")),
                "condo_fee": self._to_float(house_info.get("condoPrice")),
                "amenities": amenities,
                "allow_pets": self._to_bool(house_info.get("acceptsPets")),
                "furnished": self._to_bool(house_info.get("hasFurniture")),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_listing_urls(self, raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        pattern = re.compile(r'"url":"(https://www\.quintoandar\.com\.br/imovel/[^"]+/comprar/[^"]+)"')
        for match in pattern.findall(raw_html):
            url = html.unescape(match).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return urls

    def _extract_house_info(self, raw_html: str) -> Optional[dict[str, Any]]:
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw_html, re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        state = (((payload.get("props") or {}).get("pageProps") or {}).get("initialState") or {})
        house = (state.get("house") or {}).get("houseInfo")
        return house if isinstance(house, dict) else None

    def _build_title(self, house_info: dict[str, Any], neighborhood: Optional[str], city: Optional[str]) -> str:
        property_type = self._normalize_text(house_info.get("type"), fallback="Casa")
        bedrooms = self._to_int(house_info.get("bedrooms"))
        bedrooms_label = f"{bedrooms} quartos" if bedrooms and bedrooms < 5 else "5 quartos ou +"
        location = ", ".join(part for part in [neighborhood, city] if part)
        if location:
            return f"{property_type} com {bedrooms_label} à venda em {location}"
        return f"{property_type} à venda"

    def _build_description(self, house_info: dict[str, Any], page_text: Optional[str] = None) -> Optional[str]:
        generated = house_info.get("generatedDescription") or {}
        long_description = generated.get("longDescription") if isinstance(generated, dict) else None
        remarks = house_info.get("remarks")

        parts: list[str] = []
        for value in [long_description, remarks]:
            normalized = self._normalize_multiline_text(value)
            if normalized and normalized not in parts:
                parts.append(normalized)
        if not parts and page_text:
            fallback = self._extract_description_from_page_text(page_text)
            if fallback:
                parts.append(fallback)
        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _extract_description_from_page_text(page_text: str) -> Optional[str]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        if not lines:
            return None

        start_index = next((idx for idx, line in enumerate(lines) if line.startswith("Publicado há")), None)
        if start_index is None:
            start_index = next((idx for idx, line in enumerate(lines) if line.startswith("Publicado em")), None)
        if start_index is None:
            return None

        description_lines: list[str] = []
        for line in lines[start_index + 1 :]:
            lowered = line.lower()
            if lowered.startswith("itens disponíveis") or lowered.startswith("itens indisponíveis"):
                break
            if lowered.startswith("conheça o condomínio") or lowered.startswith("conheca o condominio"):
                break
            if lowered.startswith("sobre a região") or lowered.startswith("sobre a regiao"):
                break
            if lowered.startswith("proximidades") or lowered.startswith("localização"):
                break
            description_lines.append(line)

        if not description_lines:
            return None

        description = " ".join(description_lines)
        description = re.sub(r"\s+", " ", description).strip()
        description = re.sub(r"\s+([,.;:!?])", r"\1", description)
        return description or None

    def _extract_amenities(self, amenities: Any) -> list[str]:
        if not isinstance(amenities, list):
            return []
        values: list[str] = []
        for amenity in amenities:
            if not isinstance(amenity, dict):
                continue
            if self._normalize_text(amenity.get("value")) != "SIM":
                continue
            text = self._normalize_text(amenity.get("text"))
            if text and text not in values:
                values.append(text)
        return values

    def _extract_images(self, photos: Any) -> list[str]:
        if not isinstance(photos, list):
            return []
        urls: list[str] = []
        seen: set[str] = set()
        for photo in photos:
            if not isinstance(photo, dict):
                continue
            filename = self._normalize_text(photo.get("url"))
            if not filename:
                continue
            absolute = f"{self.config.base_url}/img/med/{filename}"
            if absolute in seen:
                continue
            seen.add(absolute)
            urls.append(absolute)
        return urls

    def _build_street(self, address: dict[str, Any]) -> Optional[str]:
        parts = [
            self._normalize_text(address.get("street")),
            self._normalize_text(address.get("neighborhood")),
        ]
        values = [part for part in parts if part]
        return " - ".join(values) if values else None

    @staticmethod
    def _normalize_text(value: Any, fallback: Optional[str] = None) -> Optional[str]:
        if value is None:
            return fallback
        text = html.unescape(str(value)).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    @staticmethod
    def _normalize_multiline_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value)).replace("\xa0", " ").replace("\r", "\n").replace("\t", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        return "\n".join(lines) or None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value in (None, "", 0):
            return None if value in (None, "") else float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"sim", "true", "yes", "1"}:
                return True
            if normalized in {"nao", "não", "false", "no", "0"}:
                return False
        return None

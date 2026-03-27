"""
Loft Scraper
Scrapes house sale listings from Loft using listing anchors and detail data from dehydratedState.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any, Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class LoftScraper(HTTPScraper):
    """Scraper for Loft property listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="loft",
                display_name="Loft",
                description="Scraper de casas a venda da Loft em Porto Alegre",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.loft.com.br",
            endpoint="/venda/imoveis/rs/porto-alegre",
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

        listing = self._extract_detail_listing(response.text)
        if not listing:
            return None

        address = listing.get("address") or {}
        city = self._normalize_text(address.get("city"))
        state = self._normalize_text(address.get("state"))
        neighborhood = self._normalize_text(address.get("neighborhood"))
        street = self._build_street(address)
        title = self._build_title(url, listing, neighborhood, city)
        description = self._normalize_text(listing.get("description"), multiline=True)
        property_type = self._infer_property_type(url, listing)

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
            "price": self._to_float(listing.get("price")),
            "currency": "BRL",
            "city": city,
            "state": state,
            "zip_code": self._normalize_text(address.get("postalCode")),
            "street": street,
            "location": location,
            "images": self._extract_images(listing),
            "videos": self._extract_videos(listing),
            "attributes": {
                "listing_type": "sale",
                "property_type": property_type,
                "bedrooms": self._to_int(listing.get("bedrooms")),
                "bathrooms": self._to_int(listing.get("restrooms")),
                "parking_spots": self._to_int(listing.get("parkingSpots")),
                "total_area_m2": self._to_float(listing.get("area")),
                "floor": self._to_int(listing.get("floor")),
                "condo_fee": self._to_float(listing.get("complexFee")),
                "iptu": self._to_float(listing.get("propertyTax")),
                "amenities_text": self._extract_named_items(listing.get("amenities")),
                "unit_features_text": self._extract_named_items(listing.get("unitFeatures")),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_listing_urls(self, raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for href in re.findall(r'href="(/imovel/[^"]+)"', raw_html):
            normalized = href.split("?", 1)[0]
            if "/imovel/casa-" not in normalized:
                continue
            absolute = urljoin(self.config.base_url, normalized)
            if absolute in seen:
                continue
            seen.add(absolute)
            urls.append(absolute)
        return urls

    def _extract_detail_listing(self, raw_html: str) -> Optional[dict[str, Any]]:
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw_html, re.S)
        if not next_data_match:
            return None
        try:
            payload = json.loads(next_data_match.group(1))
        except json.JSONDecodeError:
            return None

        page_props = ((payload.get("props") or {}).get("pageProps") or {})
        dehydrated_state = page_props.get("dehydratedState") or {}
        for query in dehydrated_state.get("queries") or []:
            query_key = query.get("queryKey") or []
            if not isinstance(query_key, list) or "Sales:GetRealState" not in query_key:
                continue
            data = ((query.get("state") or {}).get("data")) or {}
            if isinstance(data, dict) and data.get("id"):
                return data
        return None

    def _build_title(
        self,
        url: str,
        listing: dict[str, Any],
        neighborhood: Optional[str],
        city: Optional[str],
    ) -> str:
        property_type = "Casa de condomínio" if "condominio" in url.lower() else "Casa"
        bedrooms = self._to_int(listing.get("bedrooms"))
        bedrooms_label = f"{bedrooms} quartos" if bedrooms and bedrooms < 5 else "5 quartos ou +"
        location = ", ".join(part for part in [neighborhood, city] if part)
        return f"{property_type} com {bedrooms_label} à venda em {location}" if location else f"{property_type} à venda"

    def _infer_property_type(self, url: str, listing: dict[str, Any]) -> str:
        lowered = url.lower()
        if "condominio" in lowered:
            return "casa"
        home_type = self._normalize_text(listing.get("homeType")) or ""
        if home_type.lower() in {"house", "home"}:
            return "casa"
        property_type = self._normalize_text(listing.get("propertyType")) or ""
        if "casa" in property_type.lower():
            return "casa"
        return "casa"

    def _extract_images(self, listing: dict[str, Any]) -> list[str]:
        listing_id = self._normalize_text(listing.get("id"))
        if not listing_id:
            return []
        images: list[str] = []
        seen: set[str] = set()
        candidates: list[str] = []
        image = listing.get("image")
        if image:
            image_name = self._extract_image_filename(image)
            if image_name:
                candidates.append(image_name)
        for photo in listing.get("photos") or []:
            photo_name = self._extract_image_filename(photo)
            if photo_name:
                candidates.append(photo_name)
        for filename in candidates:
            url = f"https://content.loft.com.br/homes/{listing_id}/{filename}"
            if url in seen:
                continue
            seen.add(url)
            images.append(url)
        return images

    def _extract_videos(self, listing: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for key in ["virtualTourUrl", "videoTourUrl"]:
            value = self._normalize_text(listing.get(key))
            if value and value not in urls:
                urls.append(value)
        return urls

    def _build_street(self, address: dict[str, Any]) -> Optional[str]:
        parts = [
            self._normalize_text(address.get("streetName") or address.get("streetFullName")),
            self._normalize_text(address.get("neighborhood")),
        ]
        values = [part for part in parts if part]
        return " - ".join(values) if values else None

    @staticmethod
    def _extract_image_filename(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ("filename", "url", "imageUrl"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip().split("/")[-1]
            return None
        text = LoftScraper._normalize_text(value)
        if not text:
            return None
        return text.split("/")[-1]

    @staticmethod
    def _extract_named_items(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        for item in values:
            if isinstance(item, dict):
                text = LoftScraper._normalize_text(
                    item.get("name") or item.get("label") or item.get("value") or item.get("description")
                )
            else:
                text = LoftScraper._normalize_text(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_text(value: Any, multiline: bool = False) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value)).replace("\xa0", " ")
        text = text.replace("\r", "\n").replace("\t", " ")
        if multiline:
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s*\n\s*", "\n", text)
            lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
            lines = [line for line in lines if line]
            cleaned=[]
            for line in lines:
                line = re.sub(r"^conte[úu]do removido\s*", "", line, flags=re.IGNORECASE).strip(" -:\t")
                if line:
                    cleaned.append(line)
            return "\n".join(cleaned) or None
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
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

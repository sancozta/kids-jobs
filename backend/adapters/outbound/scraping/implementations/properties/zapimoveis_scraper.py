"""
ZapImóveis Scraper
Scrapes house sale listings from ZapImóveis using browser_playwright with headful fallback.
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
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class ZapImoveisScraper(HTTPScraper):
    """Scraper for ZapImóveis house sale listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="zapimoveis",
                display_name="ZapImóveis",
                description="Scraper de casas à venda do ZapImóveis em Porto Alegre",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.zapimoveis.com.br",
            endpoint="/venda/casas/rs%2Bporto-alegre/",
            enabled=True,
            timeout=20,
            rate_limit_delay=2.5,
            max_items_per_run=30,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_headless": False,
                "playwright_headful_fallback": True,
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3200,
            },
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

        raw_html = response.text
        product = self._extract_product_schema(raw_html)
        payload = self._extract_inline_payload(raw_html)

        title = self._extract_title(raw_html, payload) or (product or {}).get("name")
        description = self._clean_description((product or {}).get("description") or payload.get("description"))
        address = payload.get("address") or {}
        listing = payload.get("listing") or {}
        amenities = payload.get("amenities") or []
        images = self._extract_images(product, payload)

        location = None
        point = address.get("point") or listing.get("address", {}).get("point") or {}
        lat = self._parse_float(point.get("lat"))
        lon = self._parse_float(point.get("lon"))
        if lat is not None and lon is not None:
            location = {"latitude": lat, "longitude": lon}

        city = self._normalize_text(address.get("city") or listing.get("address", {}).get("city"))
        state = self._normalize_state(address.get("stateAcronym") or listing.get("address", {}).get("stateAcronym"))
        street = self._build_street(address or listing.get("address") or {})
        zip_code = self._normalize_zip(address.get("zipCode"))
        listing_type = "sale"
        property_type = self._infer_property_type(url, listing)
        main_amenities = payload.get("mainAmenities") or {}

        scraped_data = {
            "title": self._normalize_text(title),
            "description": description,
            "price": self._parse_float(((product or {}).get("offers") or {}).get("price")) or self._parse_float(
                ((listing.get("prices") or {}).get("mainValue"))
            ),
            "currency": self._normalize_text((((product or {}).get("offers") or {}).get("priceCurrency"))) or "BRL",
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "street": street,
            "location": location,
            "images": images,
            "videos": self._extract_videos(payload),
            "attributes": {
                "listing_type": listing_type,
                "property_type": property_type,
                "bedrooms": self._parse_int(main_amenities.get("bedrooms") or self._extract_bedrooms_from_title(title)),
                "bathrooms": self._parse_int(main_amenities.get("bathrooms")),
                "parking_spots": self._parse_int(main_amenities.get("parkingSpaces")),
                "total_area_m2": self._parse_float(self._extract_area(main_amenities.get("usableAreas"))),
                "amenities_text": self._normalize_string_list(amenities),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_listing_urls(self, raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for href in re.findall(r'href="(https://www\.zapimoveis\.com\.br/imovel/[^"]+)"', raw_html):
            normalized = href.split("?", 1)[0].rstrip("/")
            if "/imovel/venda-" not in normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _extract_product_schema(self, raw_html: str) -> Optional[dict[str, Any]]:
        for match in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', raw_html, re.S):
            try:
                data = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
        return None

    def _extract_inline_payload(self, raw_html: str) -> dict[str, Any]:
        for marker in ('baseData":{"pageData":', 'baseData\\":{\\"pageData\\":'):
            start = raw_html.find(marker)
            if start < 0:
                continue

            segment = raw_html[start + len(marker) - 1 :]
            depth = 0
            end_index = None
            for index, char in enumerate(segment):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end_index = index + 1
                        break
            if end_index is None:
                continue

            raw_json = segment[:end_index]
            decoded = bytes(raw_json, "utf-8").decode("unicode_escape")
            decoded = decoded.replace('\\"', '"').replace("\\/", "/")
            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                continue
        return self._extract_inline_payload_fallback(raw_html)

    def _extract_inline_payload_fallback(self, raw_html: str) -> dict[str, Any]:
        def find(pattern: str) -> Optional[str]:
            match = re.search(pattern, raw_html, re.I)
            return match.group(1) if match else None

        address = {
            "zipCode": find(r'(?:\\"|")zipCode(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "city": find(r'(?:\\"|")city(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "streetNumber": find(r'(?:\\"|")streetNumber(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "stateAcronym": find(r'(?:\\"|")stateAcronym(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "street": find(r'(?:\\"|")street(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "neighborhood": find(r'(?:\\"|")neighborhood(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
        }
        lat = find(r'(?:\\"|")lat(?:\\"|")\s*:\s*(-?\d+(?:\.\d+)?)')
        lon = find(r'(?:\\"|")lon(?:\\"|")\s*:\s*(-?\d+(?:\.\d+)?)')
        if lat and lon:
            address["point"] = {"lat": lat, "lon": lon}

        prices = {
            "mainValue": find(r'(?:\\"|")mainValue(?:\\"|")\s*:\s*(\d+(?:\.\d+)?)'),
            "iptu": find(r'(?:\\"|")iptu(?:\\"|")\s*:\s*(\d+(?:\.\d+)?)'),
            "condominium": find(r'(?:\\"|")condominium(?:\\"|")\s*:\s*(\d+(?:\.\d+)?)'),
        }
        main_amenities = {
            "usableAreas": find(r'(?:\\"|")usableAreas(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "bedrooms": find(r'(?:\\"|")bedrooms(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "bathrooms": find(r'(?:\\"|")bathrooms(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
            "parkingSpaces": find(r'(?:\\"|")parkingSpaces(?:\\"|")\s*:\s*(?:\\"|")([^"\\]+)'),
        }

        videos = [{"url": url} for url in re.findall(r'(https://www\.youtube\.com/watch\?v=[^"\\]+)', raw_html)]
        amenities = re.findall(r'(?:\\"|")([A-Z_]{3,})(?:\\"|")', find(r'(?:\\"|")amenities(?:\\"|")\s*:\s*\[(.*?)\]') or "")
        image_list = [
            {"dangerousSrc": value}
            for value in re.findall(
                r'(https://resizedimgs\.zapimoveis\.com\.br/img/vr-listing/[^"\\]+)',
                raw_html,
            )
        ]

        return {
            "address": address,
            "listing": {
                "prices": prices,
                "amenities": amenities,
                "imageList": image_list,
                "unitTypes": [find(r'(?:\\"|")unitTypes(?:\\"|")\s*:\s*\[\s*(?:\\"|")([^"\\]+)') or ""],
            },
            "mainAmenities": main_amenities,
            "videos": videos,
        }

    def _extract_title(self, raw_html: str, payload: dict[str, Any]) -> Optional[str]:
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, re.S | re.I)
        if h1_match:
            return self._normalize_text(re.sub(r"<[^>]+>", " ", h1_match.group(1)))
        meta = (payload.get("metaContent") or {}).get("title")
        return self._normalize_text(meta)

    def _extract_images(self, product: Optional[dict[str, Any]], payload: dict[str, Any]) -> list[str]:
        images: list[str] = []
        seen: set[str] = set()

        for url in (product or {}).get("image") or []:
            normalized = self._normalize_image_url(url)
            if normalized and normalized not in seen:
                seen.add(normalized)
                images.append(normalized)

        page_data = payload.get("listing") or {}
        for image in page_data.get("imageList") or []:
            normalized = self._normalize_image_url((image or {}).get("dangerousSrc"))
            if normalized and normalized not in seen:
                seen.add(normalized)
                images.append(normalized)
        return images

    def _extract_videos(self, payload: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        for video in payload.get("videos") or []:
            url = self._normalize_text((video or {}).get("url"))
            if url and url not in urls:
                urls.append(url)
        return urls

    def _build_street(self, address: dict[str, Any]) -> Optional[str]:
        parts = [
            self._normalize_text(address.get("street")),
            self._normalize_text(address.get("streetNumber")),
            self._normalize_text(address.get("neighborhood")),
        ]
        values = [part for part in parts if part]
        if len(values) >= 3:
            return f"{values[0]}, {values[1]} - {values[2]}"
        if len(values) == 2:
            return f"{values[0]} - {values[1]}"
        return values[0] if values else None

    def _infer_property_type(self, url: str, listing: dict[str, Any]) -> str:
        lowered = url.lower()
        if "casa-de-condominio" in lowered or "/venda-casa-de-condominio-" in lowered:
            return "casa"
        unit_types = listing.get("unitTypes") or []
        normalized_types = {self._normalize_text(item) for item in unit_types if self._normalize_text(item)}
        if "HOME" in normalized_types or "Casa" in normalized_types:
            return "casa"
        return "casa"

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value)).replace("\xa0", " ").replace("\r", "\n").replace("\t", " ")
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _normalize_state(value: Any) -> Optional[str]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        if len(text) == 2:
            return text.upper()
        parts = text.split()
        if len(parts) >= 3 and parts[0].lower() == "rio" and parts[1].lower() == "grande":
            return "RS"
        return text[:2].upper()

    @staticmethod
    def _normalize_zip(value: Any) -> Optional[str]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        digits = re.sub(r"\D", "", text)
        return digits or None

    @staticmethod
    def _normalize_image_url(value: Any) -> Optional[str]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        return text.replace("{description}", "imagem").replace("{action}", "fit-in").replace("{width}", "1024").replace(
            "{height}", "768"
        )

    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None

    @staticmethod
    def _extract_area(value: Any) -> Optional[str]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        match = re.search(r"\d+(?:[.,]\d+)?", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_bedrooms_from_title(value: Any) -> Optional[int]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        match = re.search(r"(\d+)\s+quartos?", text, re.I)
        return int(match.group(1)) if match else None

    @staticmethod
    def _clean_description(value: Any) -> Optional[str]:
        text = ZapImoveisScraper._normalize_text(value)
        if not text:
            return None
        text = re.sub(r"Veja outros imóveis no site.*$", "", text, flags=re.I).strip()
        text = re.sub(r"Fale com nossos consultores.*$", "", text, flags=re.I).strip()
        return text or None

    @staticmethod
    def _normalize_string_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        for item in values:
            text = ZapImoveisScraper._normalize_text(item)
            if text and text not in normalized:
                normalized.append(text.lower())
        return normalized

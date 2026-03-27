"""OLX vehicle scraper using browser-rendered list/detail pages."""
from __future__ import annotations

import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class OLXVehiclesScraper(HTTPScraper):
    """Scraper for OLX vehicle listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="olx_vehicles",
                display_name="OLX Veículos",
                description="Scraper de veículos da OLX com extração por detalhe",
                category=ScrapingCategory.VEHICLES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.olx.com.br",
            endpoint="/autos-e-pecas/carros-vans-e-utilitarios/estado-df/distrito-federal-e-regiao/brasilia",
            enabled=False,
            timeout=40,
            rate_limit_delay=2.5,
            max_items_per_run=30,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_headless": True,
                "playwright_headful_fallback": False,
                "playwright_persistent_session": False,
                "playwright_wait_until": "commit",
                "playwright_wait_after_load_ms": 1200,
                "playwright_infinite_scroll_enabled": False,
                "playwright_infinite_scroll_max_rounds": 6,
                "playwright_infinite_scroll_pause_ms": 1200,
                "playwright_infinite_scroll_stable_rounds": 2,
                "playwright_warmup_url": "https://www.olx.com.br/estado-df/distrito-federal-e-regiao",
                "playwright_virtual_display_size": "1280x800",
                "playwright_block_resource_types": ["image", "media", "font", "stylesheet"],
                "playwright_retry_count": 3,
                "playwright_retry_delay_ms": 1200,
                "playwright_block_url_patterns": [
                    "googletagmanager",
                    "google-analytics",
                    "doubleclick",
                    "facebook.net",
                    "connect.facebook",
                    "hotjar",
                    "clarity.ms",
                    "ads-twitter",
                    "criteo",
                ],
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return items

        for url in self._extract_listing_urls(response.text):
            item = self.scrape_url(url)
            if item:
                items.append(item)
            if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                break
        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_url = (url or "").strip().split("?", 1)[0]
        if not normalized_url:
            return None

        response = self.fetch_page(normalized_url)
        if not response:
            return None
        return self._parse_detail_page(normalized_url, response.text)

    def _extract_listing_urls(self, raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        pattern = r"https://[a-z]{2}\.olx\.com\.br/[^\"'\s]+/autos-e-pecas/carros-vans-e-utilitarios/[^\"'\s]+-\d+"
        for match in re.findall(pattern, raw_html, re.I):
            normalized = match.split("?", 1)[0].rstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _parse_detail_page(self, url: str, raw_html: str) -> Optional[ScrapedItem]:
        if "Attention Required! | Cloudflare" in raw_html or "Sorry, you have been blocked" in raw_html:
            return None

        soup = self.parse_html(raw_html)
        page_text = soup.get_text("\n", strip=True)
        title = self._extract_title(raw_html, page_text)
        if not title:
            return None

        details = self._extract_key_value_pairs(page_text)
        description = self._extract_description(page_text, title)
        city, state, zip_code = self._extract_location(page_text)
        price = self._extract_main_price(page_text)
        images = self._extract_images(raw_html)
        features = self._extract_block_items(page_text, "Opcionais deste veículo", "Outras Características")
        extra_features = self._extract_block_items(page_text, "Outras Características", "Localização")
        all_features = []
        seen: set[str] = set()
        for item in features + extra_features:
            if item not in seen:
                seen.add(item)
                all_features.append(item)

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "images": images,
            "attributes": {
                "brand": details.get("Marca"),
                "model": self._normalize_model(details.get("Modelo"), details.get("Marca")),
                "version": self._extract_version_from_title(
                    title,
                    self._normalize_model(details.get("Modelo"), details.get("Marca")),
                ),
                "body_type": details.get("Tipo de veículo"),
                "year": details.get("Ano"),
                "mileage": details.get("Quilometragem"),
                "engine": details.get("Potência do motor"),
                "fuel_type": details.get("Combustível"),
                "transmission": details.get("Câmbio"),
                "color": details.get("Cor"),
                "doors": details.get("Portas"),
                "features": all_features,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_title(self, raw_html: str, page_text: str) -> Optional[str]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        title_from_head = self._extract_title_from_html(raw_html)
        title_from_head = re.sub(r"\s*-\s*\d+\s*\|\s*OLX$", "", title_from_head or "", flags=re.I).strip()

        text_candidates = [
            line
            for line in lines[:80]
            if re.search(r"\b(19\d{2}|20\d{2})\b", line)
            and " | OLX" not in line
            and "R$" not in line
            and len(line.split()) >= 4
        ]
        title_from_body = max(text_candidates, key=len, default=None)
        if title_from_body and (
            not title_from_head or len(title_from_body) > len(title_from_head) + 4
        ):
            return title_from_body
        if title_from_head:
            return title_from_head
        return lines[0] if lines else None

    def _extract_description(self, page_text: str, title: str) -> Optional[str]:
        pattern = re.escape(title) + r"\s*(.*?)\s*Histórico Veicular"
        match = re.search(pattern, page_text, re.S)
        if not match:
            match = re.search(re.escape(title) + r"\s*(.*?)\s*Detalhes", page_text, re.S)
        if not match:
            return None
        description = " ".join(part.strip() for part in match.group(1).splitlines() if part.strip())
        description = re.sub(r"\s+", " ", description).strip()
        description = re.sub(r"^-\s*\d+\s*\|\s*OLX\s*", "", description, flags=re.I).strip()
        if description.startswith(title):
            description = description[len(title):].strip()
        description = re.sub(r"\bVer descrição completa\b", "", description, flags=re.I).strip()
        return description or None

    def _extract_location(self, page_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line != "Localização":
                continue
            for candidate in lines[index + 1 : index + 8]:
                match = re.search(r"(.+?),\s*([A-Z]{2})(?:,\s*(\d{8}))?", candidate)
                if not match:
                    continue
                city, state, zip_digits = match.groups()
                return city.strip().title(), state.upper(), self._format_zip_code(zip_digits)

        if "Carros, vans e utilitários" in lines:
            category_index = lines.index("Carros, vans e utilitários")
            if category_index + 1 < len(lines):
                city = lines[category_index + 1].strip().title()
                state = self._infer_state_from_breadcrumb(lines[: category_index + 1])
                if city:
                    return city, state, None
        return None, None, None

    def _extract_main_price(self, page_text: str) -> Optional[float]:
        matches = []
        for value in re.findall(r"R\$\s*([\d\.]+(?:,\d{2})?)", page_text[:2500]):
            parsed = self.parse_price(value)
            if parsed is not None:
                matches.append(parsed)
        if not matches:
            return None
        if len(matches) >= 2 and matches[0] >= 10000 and matches[1] >= 10000:
            return min(matches[0], matches[1])
        for value in matches:
            if value >= 10000:
                return value
        return min(matches)

    @staticmethod
    def _extract_images(raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for match in re.findall(r"&quot;original&quot;:&quot;(https://img\.olx\.com\.br/images/[^&]+?\.jpg)", raw_html, re.I):
            normalized = match.replace("&amp;", "&")
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)

        if urls:
            return urls[:30]

        pattern = r"https://[^\"'>\s]+\.(?:jpg|jpeg|png|webp)(?:\?[^\"'>\s]+)?"
        for match in re.findall(pattern, raw_html, re.I):
            normalized = match.replace("&amp;", "&")
            if (
                "static.olx" in normalized
                or "/assets/" in normalized
                or "thumbs" in normalized
                or "olx.com.br/" in normalized
            ):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls[:30]

    @staticmethod
    def _extract_key_value_pairs(page_text: str) -> dict[str, str]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        labels = {
            "Categoria",
            "Modelo",
            "Marca",
            "Tipo de veículo",
            "Ano",
            "Quilometragem",
            "Potência do motor",
            "Combustível",
            "Câmbio",
            "Direção",
            "Cor",
            "Portas",
            "Final de placa",
            "Possui Kit GNV",
            "Tipo de direção",
        }
        pairs: dict[str, str] = {}
        for index, line in enumerate(lines[:-1]):
            if line in labels:
                value = lines[index + 1]
                if value and value not in labels:
                    pairs[line] = value
        return pairs

    @staticmethod
    def _extract_block_items(page_text: str, start_label: str, end_label: str) -> list[str]:
        match = re.search(re.escape(start_label) + r"(.*?)" + re.escape(end_label), page_text, re.S | re.I)
        if not match:
            return []
        items: list[str] = []
        seen: set[str] = set()
        for line in [item.strip() for item in match.group(1).splitlines() if item.strip()]:
            if len(line) <= 1:
                continue
            if line in {start_label, end_label, "Fechar janela de diálogo"}:
                continue
            if line.lower().startswith("exibir todas"):
                continue
            if line in seen:
                continue
            seen.add(line)
            items.append(line)
        return items

    @staticmethod
    def _extract_version_from_title(title: str, model: Optional[str]) -> Optional[str]:
        if not title:
            return None
        normalized_model = (model or "").strip()
        if normalized_model and normalized_model in title:
            version = title.split(normalized_model, 1)[-1].strip()
            return version or None
        parts = title.split()
        if len(parts) > 2:
            return " ".join(parts[2:]).strip()
        return None

    @staticmethod
    def _format_zip_code(value: Optional[str]) -> Optional[str]:
        digits = re.sub(r"\D", "", value or "")
        if len(digits) != 8:
            return None
        return f"{digits[:5]}-{digits[5:]}"

    def _infer_state_from_breadcrumb(self, lines: list[str]) -> Optional[str]:
        for line in reversed(lines):
            normalized = line.strip().lower()
            if normalized in self.BRAZIL_STATE_NAME_TO_UF:
                return self.BRAZIL_STATE_NAME_TO_UF[normalized]
        return None

    @staticmethod
    def _normalize_model(model: Optional[str], brand: Optional[str]) -> Optional[str]:
        text = (model or "").strip()
        if not text:
            return None
        brand_text = (brand or "").strip()
        if brand_text and text.lower().startswith(brand_text.lower() + " "):
            text = text[len(brand_text) :].strip()
        return text or None

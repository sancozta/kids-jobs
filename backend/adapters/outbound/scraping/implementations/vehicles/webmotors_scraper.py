"""WebMotors vehicle scraper using browser-rendered list/detail pages."""
from __future__ import annotations

import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class WebMotorsScraper(HTTPScraper):
    """Scraper for WebMotors vehicle listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="webmotors",
                display_name="WebMotors",
                description="Scraper de veículos da WebMotors com extração por detalhe",
                category=ScrapingCategory.VEHICLES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.webmotors.com.br",
            endpoint="/carros/estoque?tipoveiculo=carros&estadocidade=estoque",
            enabled=False,
            timeout=40,
            rate_limit_delay=2.5,
            max_items_per_run=30,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_headless": True,
                "playwright_headful_fallback": True,
                "playwright_persistent_session": False,
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3500,
                "playwright_infinite_scroll_enabled": True,
                "playwright_infinite_scroll_max_rounds": 6,
                "playwright_infinite_scroll_pause_ms": 1000,
                "playwright_infinite_scroll_stable_rounds": 2,
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
        pattern = r"https://www\.webmotors\.com\.br/comprar/[a-z0-9\-_/]+/\d+"
        for match in re.findall(pattern, raw_html, re.I):
            normalized = match.split("?", 1)[0].rstrip("/")
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _parse_detail_page(self, url: str, raw_html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(raw_html)
        title = self.extract_text(soup, "h1") or self._extract_title_from_html(raw_html)
        if not title:
            return None

        page_text = soup.get_text("\n", strip=True)
        details = self._extract_key_value_pairs(page_text)
        price = self._extract_main_price(page_text)
        city, state = self._extract_city_state(details.get("Cidade"))
        description = self._build_description(title, details, page_text)
        images = self._extract_images(raw_html)
        features = self._extract_features(page_text)

        year_text = details.get("Ano")
        year = None
        if year_text:
            years = re.findall(r"\b(19\d{2}|20\d{2})\b", year_text)
            if years:
                year = years[-1]

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "city": city,
            "state": state,
            "images": images,
            "attributes": {
                "brand": self._extract_brand_from_title(title),
                "model": self._extract_model_from_title(title),
                "version": self._extract_version_from_title(title),
                "year": year,
                "mileage": details.get("KM"),
                "transmission": details.get("Câmbio"),
                "body_type": details.get("Carroceria"),
                "fuel_type": details.get("Combustível"),
                "color": details.get("Cor"),
                "features": features,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_key_value_pairs(page_text: str) -> dict[str, str]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        pairs: dict[str, str] = {}
        labels = {
            "Cidade",
            "Ano",
            "KM",
            "Câmbio",
            "Carroceria",
            "Combustível",
            "Cor",
            "Final de placa",
            "Aceita troca",
        }
        for index, line in enumerate(lines[:-1]):
            if line in labels:
                value = lines[index + 1]
                if value and value not in labels:
                    pairs[line] = value
        return pairs

    def _extract_main_price(self, page_text: str) -> Optional[float]:
        matches = re.findall(r"R\$\s*([\d\.]+(?:,\d{2})?)", page_text)
        if not matches:
            return None
        candidates = [self.parse_price(match) for match in matches[:4]]
        candidates = [value for value in candidates if value is not None]
        if not candidates:
            return None
        return min(candidates)

    @staticmethod
    def _extract_city_state(raw_value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not raw_value:
            return None, None
        match = re.search(r"(.+?)\s*-\s*([A-Z]{2})", raw_value)
        if not match:
            return raw_value.strip(), None
        return match.group(1).strip().title(), match.group(2).upper()

    def _build_description(self, title: str, details: dict[str, str], page_text: str) -> str:
        description_lines = [title]
        city = details.get("Cidade")
        if city:
            description_lines.append(f"Localização: {city}")
        if details.get("Ano"):
            description_lines.append(f"Ano: {details['Ano']}")
        if details.get("KM"):
            description_lines.append(f"KM: {details['KM']}")
        if details.get("Câmbio"):
            description_lines.append(f"Câmbio: {details['Câmbio']}")
        if details.get("Combustível"):
            description_lines.append(f"Combustível: {details['Combustível']}")
        if details.get("Carroceria"):
            description_lines.append(f"Carroceria: {details['Carroceria']}")
        feature_lines = self._extract_features(page_text)
        if feature_lines:
            description_lines.append("Opcionais: " + ", ".join(feature_lines[:12]))
        return "\n".join(description_lines)

    @staticmethod
    def _extract_images(raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        pattern = r"https://(?:image|img)\.webmotors\.com\.br/[^\"'>\s]+"
        for match in re.findall(pattern, raw_html, re.I):
            normalized = match.replace("&amp;", "&")
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    @staticmethod
    def _extract_features(page_text: str) -> list[str]:
        block_match = re.search(r"Itens de veículo(.*?)Confiança e tranquilidade", page_text, re.S | re.I)
        if not block_match:
            block_match = re.search(r"Itens de veículo(.*?)Sobre o vendedor", page_text, re.S | re.I)
        if not block_match:
            return []
        features: list[str] = []
        seen: set[str] = set()
        for line in [item.strip() for item in block_match.group(1).splitlines() if item.strip()]:
            if len(line) < 2 or line.lower().startswith("itens de veículo"):
                continue
            if line in seen:
                continue
            seen.add(line)
            features.append(line)
        return features

    @staticmethod
    def _extract_brand_from_title(title: str) -> Optional[str]:
        parts = title.split()
        return parts[0].title() if parts else None

    @staticmethod
    def _extract_model_from_title(title: str) -> Optional[str]:
        parts = title.split()
        if len(parts) < 2:
            return None
        if len(parts) >= 3 and parts[1].upper() == parts[1] and parts[2].upper() == parts[2]:
            return f"{parts[1].title()} {parts[2].title()}"
        return parts[1].title()

    @staticmethod
    def _extract_version_from_title(title: str) -> Optional[str]:
        parts = title.split()
        if len(parts) <= 3:
            return None
        return " ".join(parts[3:]).strip().title()

"""Las Colonias supplements scraper."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class LasColoniasScraper(HTTPScraper):
    """Scraper for Las Colonias wholesale supplement catalog."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="lascolonias",
                display_name="Las Colonias",
                description="Catálogo atacadista de suplementos com produtos, marcas e variações",
                category=ScrapingCategory.SUPPLEMENTS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.lascolonias.com.br",
            endpoint="/produtos",
            enabled=True,
            rate_limit_delay=1.0,
            max_items_per_run=20,
        )

    def scrape(self) -> list[ScrapedItem]:
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return []

        urls = self._extract_product_urls(response.text)
        items: list[ScrapedItem] = []
        for url in urls:
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
        return self._parse_product_page(normalized_url, response.text)

    def _extract_product_urls(self, raw_html: str) -> list[str]:
        soup = self.parse_html(raw_html)
        urls: list[str] = []
        seen: set[str] = set()

        for link in soup.select("a[href^='produto/'], a[href*='/produto/']"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(f"{self.config.base_url}/", href).split("?", 1)[0]
            if "/produto/" not in full_url:
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            urls.append(full_url)
        return urls

    def _parse_product_page(self, url: str, raw_html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(raw_html)

        title = self._extract_title(soup, raw_html)
        if not title:
            return None

        brand = self._extract_labeled_value(soup, "Marca:")
        category = self._extract_labeled_value(soup, "Categoria:")
        package_sizes = self._extract_section_values(soup, "EMBALAGENS")
        flavors = self._extract_section_values(soup, "SABORES")
        description = self._extract_description(soup)
        images = self._extract_images(soup)
        meta_description = self._extract_meta_description(soup)

        if flavors:
            flavor_text = ", ".join(flavors)
            description = f"{description}\n\nSabores: {flavor_text}".strip() if description else f"Sabores: {flavor_text}"
        if meta_description and meta_description not in (description or ""):
            description = f"{description}\n\n{meta_description}".strip() if description else meta_description

        scraped_data = {
            "title": title,
            "description": description,
            "price": None,
            "currency": "BRL",
            "images": images,
            "attributes": {
                "product_type": self._infer_product_type(title=title, category=category, description=description),
                "package_size": ", ".join(package_sizes) if package_sizes else None,
                "white_label": self._infer_white_label(raw_html),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_title(soup, raw_html: str) -> Optional[str]:
        node = soup.select_one("h1.product-h1, #top-produtos h1, title")
        if node:
            text = " ".join(node.get_text(" ", strip=True).split())
            text = re.sub(r"\s+Nutrata$", "", text, flags=re.I).strip()
            return text or None
        title = HTTPScraper._extract_title_from_html(raw_html)
        title = re.sub(r"\s+Nutrata$", "", title, flags=re.I).strip()
        return title or None

    @staticmethod
    def _extract_labeled_value(soup, label_prefix: str) -> Optional[str]:
        for selector in ("h2.factory-title", "h3.category-title"):
            for node in soup.select(selector):
                text = " ".join(node.get_text(" ", strip=True).split())
                if text.startswith(label_prefix):
                    return text.replace(label_prefix, "", 1).strip() or None
        return None

    @staticmethod
    def _extract_section_values(soup, heading: str) -> list[str]:
        for node in soup.select("#img-descriptions h5"):
            text = " ".join(node.get_text(" ", strip=True).split()).upper()
            if text != heading.upper():
                continue
            container = node.parent
            values: list[str] = []
            for cleaned in [" ".join(part.split()).strip() for part in container.stripped_strings]:
                if not cleaned or cleaned.upper() == heading.upper():
                    continue
                values.append(cleaned)
            return values
        return []

    @staticmethod
    def _extract_description(soup) -> Optional[str]:
        node = soup.select_one("#text-descriptions")
        if not node:
            return None
        text = node.get_text("\n", strip=True)
        text = re.sub(r"\n{2,}", "\n\n", text).strip()
        return text or None

    @staticmethod
    def _extract_images(soup) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for img in soup.select(".getProduct img[src], .slider-for img[src]"):
            src = (img.get("src") or "").strip()
            if not src:
                continue
            full_url = urljoin("https://www.lascolonias.com.br/", src)
            if full_url in seen:
                continue
            seen.add(full_url)
            urls.append(full_url)
        return urls[:20]

    @staticmethod
    def _extract_meta_description(soup) -> Optional[str]:
        node = soup.select_one("meta[name='description'][content]")
        if not node:
            return None
        text = " ".join((node.get("content") or "").split()).strip()
        return text or None

    @staticmethod
    def _infer_product_type(*, title: str, category: Optional[str], description: Optional[str]) -> Optional[str]:
        fingerprint = " ".join(filter(None, [title, category, description])).lower()
        if "caps" in fingerprint or "cáps" in fingerprint or "capsul" in fingerprint:
            return "capsula"
        if "goma" in fingerprint:
            return "goma"
        if "liquid" in fingerprint or "líquid" in fingerprint or "bebida" in fingerprint or "shake" in fingerprint:
            return "liquido"
        if "tablete" in fingerprint or "comprim" in fingerprint:
            return "comprimido"
        if any(token in fingerprint for token in ("whey", "creatina", "bcaa", "glutamina", "protein", "powder", "pó", "po ")):
            return "po"
        return "outro"

    @staticmethod
    def _infer_white_label(raw_html: str) -> Optional[bool]:
        text = raw_html.lower()
        if any(keyword in text for keyword in ("white label", "marca própria", "marca propria")):
            return True
        return None

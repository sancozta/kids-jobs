"""
DF Imoveis Scraper
Scrapes house sale listings from DF Imoveis and enriches data from the detail page.
"""
import html
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class DfImoveisScraper(HTTPScraper):
    """Scraper for DF Imoveis property listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="dfimoveis",
                display_name="DF Imoveis",
                description="Scraper de casas a venda em Brasilia no DF Imoveis",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.dfimoveis.com.br",
            endpoint="/venda/df/brasilia/casa",
            enabled=True,
            rate_limit_delay=2.5,
            max_items_per_run=40,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            response = self.fetch_page(self.config.get_full_url())
            if not response:
                return items

            soup = self.parse_html(response.text)
            seen_urls: set[str] = set()
            for anchor in soup.select('a[href*="/imovel/"]'):
                href = (anchor.get("href") or "").strip()
                url = self._normalize_detail_url(href)
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                item = self.scrape_url(url)
                if item:
                    items.append(item)
                if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                    break

            self.logger.info("Scraped %s items from DF Imoveis", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping DF Imoveis: %s", exc)
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        response = self.fetch_page(url)
        if not response:
            return None

        soup = self.parse_html(response.text)
        raw_html = response.text
        title = self._extract_title(soup, raw_html, url)
        description = self._extract_description(soup)
        price_text = self._extract_price_text(raw_html)
        location_text = self._extract_location_text(soup, raw_html)
        city, state, street = self._parse_location(location_text)
        latitude, longitude = self._extract_coordinates(raw_html)
        images = self._extract_images(soup)
        area_m2 = self._extract_number(raw_html, r"Área Útil:</span>\s*<h4[^>]*>\s*([\d\.,]+)")
        bedrooms = self._extract_int(raw_html, r"com\s+(\d+)\s+quartos?")
        bathrooms = self._extract_int(description or "", r"(\d+)\s+Banheiros?\s+sociais?")
        garage_spots = self._extract_int(description or "", r"garagem\s+para\s+(\d+)\s+carros?")
        property_type = self._infer_property_type(url, title)

        scraped_data = {
            "title": title,
            "description": description,
            "price": self.parse_price(price_text),
            "currency": "BRL",
            "city": city,
            "state": state,
            "street": street,
            "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
            "images": images,
            "attributes": {
                "listing_type": "sale",
                "property_type": property_type,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "parking_spots": garage_spots,
                "total_area_m2": area_m2,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _normalize_detail_url(self, href: str) -> Optional[str]:
        if not href or "/imovel/" not in href:
            return None
        normalized = urljoin(self.config.base_url, href).split("?", 1)[0]
        return normalized.rstrip("/")

    @staticmethod
    def _extract_title(soup, raw_html: str, url: str) -> str:
        meta_title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', raw_html, re.IGNORECASE)
        if meta_title_match:
            content = DfImoveisScraper._normalize_text(meta_title_match.group(1))
            content = re.sub(r"\s*-\s*R\$\s*[\d\.\,]+.*$", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"\s*-\s*DFimoveis\.com$", "", content, flags=re.IGNORECASE).strip()
            content = content.rstrip("- ").strip()
            if content:
                return content

        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and meta_title.get("content"):
            content = DfImoveisScraper._normalize_text(meta_title["content"])
            content = re.sub(r"\s*-\s*R\$\s*[\d\.\,]+.*$", "", content, flags=re.IGNORECASE).strip()
            content = re.sub(r"\s*-\s*DFimoveis\.com$", "", content, flags=re.IGNORECASE).strip()
            content = content.rstrip("- ").strip()
            if content:
                return content

        heading = soup.select_one("h1")
        if heading:
            text = " ".join(heading.get_text(" ", strip=True).split())
            if text:
                return text

        slug = url.rstrip("/").rsplit("/", 1)[-1]
        return slug.replace("-", " ").strip().title()

    @staticmethod
    def _extract_description(soup) -> Optional[str]:
        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = DfImoveisScraper._normalize_text(heading.get_text(" ", strip=True)).lower()
            if heading_text != "descrição":
                continue
            card = heading.find_parent(
                lambda tag: tag.name in {"div", "section", "article"}
                and tag.get("class")
                and "imv-card" in tag.get("class", [])
            )
            if not card:
                continue

            for removable in card.select("button, a.btn, .show-more, .hide-more"):
                removable.decompose()

            content_container = (
                card.select_one(".assined-imv")
                or card.select_one(".d-flex.flex-column.gap-3.align-items-start.justify-content-center")
                or card
            )
            raw_text = content_container.get_text("\n", strip=True)
            description = DfImoveisScraper._normalize_text(raw_text, multiline=True)
            description = re.sub(
                r"(?im)^(crítica?r o anúncio|folder do imóvel|imprimir folder do imóvel.*)$",
                "",
                description,
            )
            description = re.sub(r"\n{3,}", "\n\n", description).strip()
            if description and description.lower() != "descrição":
                return html.unescape(description)
        return None

    @staticmethod
    def _extract_price_text(raw_html: str) -> Optional[str]:
        match = re.search(r"<span[^>]*>\s*R\$\s*</span>\s*<h4[^>]*>\s*([\d\.\,]+)", raw_html, re.IGNORECASE)
        if match:
            return f"R$ {match.group(1).strip()}"

        fallback = re.search(r"R\$\s*([\d\.\,]+)", raw_html, re.IGNORECASE)
        if fallback:
            return f"R$ {fallback.group(1).strip()}"
        return None

    @staticmethod
    def _extract_location_text(soup, raw_html: str) -> Optional[str]:
        location_node = soup.select_one(".imv-map h4")
        if location_node:
            return " ".join(location_node.get_text(" ", strip=True).split())

        city = DfImoveisScraper._extract_data_attr(raw_html, "cidade")
        state = DfImoveisScraper._extract_data_attr(raw_html, "uf")
        neighborhood = DfImoveisScraper._extract_data_attr(raw_html, "bairro")
        if city and state:
            return " - ".join(part for part in [state, city, neighborhood] if part)
        return None

    @staticmethod
    def _parse_location(location_text: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if not location_text:
            return None, None, None
        parts = [part.strip() for part in location_text.split("-") if part.strip()]
        if len(parts) >= 2:
            state = parts[0].upper()
            city = parts[1].title()
            street = " - ".join(parts[2:]).title() if len(parts) > 2 else None
            return city, state, street
        return None, None, location_text.title()

    @staticmethod
    def _extract_coordinates(raw_html: str) -> tuple[Optional[float], Optional[float]]:
        lat_match = re.search(r"latitude\s*=\s*(-?\d+\.\d+)", raw_html, re.IGNORECASE)
        lon_match = re.search(r"longitude\s*=\s*(-?\d+\.\d+)", raw_html, re.IGNORECASE)
        latitude = float(lat_match.group(1)) if lat_match else None
        longitude = float(lon_match.group(1)) if lon_match else None
        return latitude, longitude

    @staticmethod
    def _extract_images(soup) -> list[str]:
        images: list[str] = []
        seen: set[str] = set()
        for image in soup.select(".swiper-slide img, meta[property='og:image']"):
            src = image.get("content") if image.name == "meta" else image.get("src")
            normalized = (src or "").strip()
            if not normalized or normalized in seen or "logo" in normalized.lower():
                continue
            seen.add(normalized)
            images.append(normalized)
        return images

    @staticmethod
    def _normalize_text(value: str, multiline: bool = False) -> str:
        text = html.unescape(value or "")
        text = text.replace("\xa0", " ").replace("\t", " ").replace("\r", "\n")
        if multiline:
            lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
            lines = [line for line in lines if line]
            return "\n".join(lines)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_number(text: str, pattern: str) -> Optional[float]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        raw = match.group(1).replace(".", "").replace(",", ".").strip()
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _extract_int(text: str, pattern: str) -> Optional[int]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_data_attr(raw_html: str, attr_name: str) -> Optional[str]:
        match = re.search(rf'data-{re.escape(attr_name)}="([^"]+)"', raw_html, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
        return None

    @staticmethod
    def _infer_property_type(url: str, title: str) -> str:
        combined = f"{url} {title}".lower()
        if "condominio" in combined:
            return "casa"
        if "chacara" in combined or "chácar" in combined:
            return "chacara"
        if "fazenda" in combined:
            return "fazenda"
        if "sitio" in combined or "sítio" in combined:
            return "sitio"
        return "casa"

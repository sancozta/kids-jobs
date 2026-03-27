"""OLX property scraper using browser-rendered list/detail pages."""
from __future__ import annotations

import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class OLXImoveisScraper(HTTPScraper):
    """Scraper for OLX house-for-sale listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="olx_imoveis",
                display_name="OLX Imóveis",
                description="Scraper de casas à venda na OLX com extração por detalhe",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.olx.com.br",
            endpoint="/imoveis/venda/casas/estado-df/distrito-federal-e-regiao/brasilia?pe=1000000&sf=1&rts=300&rts=303",
            enabled=True,
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
        pattern = r"https://[a-z]{2}\.olx\.com\.br/[^\"'\s]+/imoveis/[^\"'\s]+-\d+"
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

        description = self._extract_description(page_text, title)
        street, city, state, zip_code = self._extract_location(page_text)
        price = self._extract_main_price(page_text)
        condo_fee = self._extract_condo_fee(page_text)
        images = self._extract_images(raw_html)
        details = self._extract_detail_pairs(page_text)
        property_features = self._extract_block_items(page_text, "Características do imóvel", "Características do condomínio")
        condo_features = self._extract_block_items(page_text, "Características do condomínio", "Código do anúncio")
        contact_name = self._extract_contact_name(page_text)
        property_type = self._infer_property_type(title, property_features, condo_features)

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "street": street,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "contact_name": contact_name,
            "images": images,
            "attributes": {
                "listing_type": "sale",
                "property_type": property_type,
                "bedrooms": self.parse_int(details.get("Quartos")),
                "bathrooms": self.parse_int(details.get("Banheiros")),
                "parking_spots": self.parse_int(details.get("Vagas na garagem")),
                "building_area_m2": self._parse_area_m2(details.get("Área construída")),
                "condo_fee": condo_fee,
                "property_features": property_features,
                "condo_features": condo_features,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_title(self, raw_html: str, page_text: str) -> Optional[str]:
        title_from_head = self._extract_title_from_html(raw_html)
        title_from_head = re.sub(r"\s*\|\s*OLX$", "", title_from_head or "", flags=re.I).strip()
        title_from_head = re.sub(r"\s+\d{6,}\s*$", "", title_from_head).strip()
        if title_from_head and not re.search(r"^Casas à venda\b", title_from_head, re.I):
            return title_from_head

        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line == "Localização" and idx >= 1:
                for offset in range(1, 5):
                    back_idx = idx - offset
                    if back_idx < 0:
                        break
                    candidate = lines[back_idx].strip()
                    if not candidate or candidate.lower() == "ver descrição completa":
                        continue
                    if candidate.lower() in {"simular consórcio agora", "simular consorcio agora"}:
                        continue
                    if any(symbol in candidate for symbol in ".?!:"):
                        continue
                    if len(candidate.split()) >= 3:
                        return candidate

        return lines[0] if lines else None

    def _extract_description(self, page_text: str, title: str) -> Optional[str]:
        match = re.search(re.escape(title) + r"\s*(.*?)\s*Localização", page_text, re.S)
        if not match:
            return None

        description = " ".join(part.strip() for part in match.group(1).splitlines() if part.strip())
        description = re.sub(r"\s+", " ", description).strip()
        description = re.sub(r"\bVer descrição completa\b", "", description, flags=re.I).strip()
        description = re.sub(r"\?+", " ", description).strip()
        description = re.sub(r"(Telefone:.*)$", "", description, flags=re.I).strip()
        return description or None

    def _extract_location(self, page_text: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line != "Localização":
                continue
            street = lines[idx + 1].strip() if idx + 1 < len(lines) else None
            locality = lines[idx + 2].strip() if idx + 2 < len(lines) else None
            if not locality:
                return street, None, None, None

            match = re.search(r"(.+?),\s*([^,]+),\s*([A-Z]{2})(?:,\s*(\d{8}))?", locality)
            if match:
                district, city, state, zip_digits = match.groups()
                normalized_street = street or district
                return normalized_street, city.strip().title(), state.upper(), self._format_zip_code(zip_digits)
            return street, None, None, None
        return None, None, None, None

    def _extract_main_price(self, page_text: str) -> Optional[float]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]

        for idx, line in enumerate(lines):
            match = re.fullmatch(r"R\$\s*([\d\.]+(?:,\d{2})?)", line)
            if not match:
                continue

            parsed = self.parse_price(match.group(1))
            if parsed is None or parsed < 10000:
                continue

            previous_window = " ".join(lines[max(0, idx - 2) : idx]).lower()
            next_window = " ".join(lines[idx + 1 : idx + 4]).lower()

            if "condomínio" in previous_window or "condominio" in previous_window or "iptu" in previous_window:
                continue

            if any(token in next_window for token in ("venda", "aluguel", "temporada", "condomínio", "condominio", "iptu")):
                return parsed

        for idx, line in enumerate(lines):
            match = re.fullmatch(r"R\$\s*([\d\.]+(?:,\d{2})?)", line)
            if not match:
                continue

            parsed = self.parse_price(match.group(1))
            if parsed is None or parsed < 10000:
                continue

            previous_window = " ".join(lines[max(0, idx - 2) : idx]).lower()
            if "condomínio" in previous_window or "condominio" in previous_window or "iptu" in previous_window:
                continue

            return parsed

        for value in re.findall(r"R\$\s*([\d\.]+(?:,\d{2})?)", page_text):
            parsed = self.parse_price(value)
            if parsed is not None and parsed >= 10000:
                return parsed
        return None

    def _extract_condo_fee(self, page_text: str) -> Optional[float]:
        match = re.search(r"Condomínio\s*R\$\s*([\d\.]+(?:,\d{2})?)", page_text, re.I)
        if not match:
            return None
        return self.parse_price(match.group(1))

    @staticmethod
    def _extract_images(raw_html: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for match in re.findall(r"&quot;original&quot;:&quot;(https://img\.olx\.com\.br/images/[^&]+?\.(?:jpg|jpeg|png|webp))", raw_html, re.I):
            normalized = match.replace("&amp;", "&")
            if normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls[:30]

    @staticmethod
    def _extract_detail_pairs(page_text: str) -> dict[str, str]:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        labels = {"Área construída", "Quartos", "Banheiros", "Vagas na garagem"}
        pairs: dict[str, str] = {}
        for idx, line in enumerate(lines[:-1]):
            if line in labels:
                value = lines[idx + 1]
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
            if len(line) <= 1 or line in {start_label, end_label, "Exibir no mapa"}:
                continue
            if line.startswith("Código do anúncio"):
                continue
            if line in seen:
                continue
            seen.add(line)
            items.append(line)
        return items

    @staticmethod
    def _extract_contact_name(page_text: str) -> Optional[str]:
        match = re.search(r"PROFISSIONAL\s+([^\n]+?)\s+Último acesso", page_text, re.S | re.I)
        if not match:
            return None
        return " ".join(match.group(1).split())

    @staticmethod
    def _parse_area_m2(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        match = re.search(r"([\d\.]+)\s*m²", value, re.I)
        if not match:
            return None
        digits = match.group(1).replace(".", "")
        try:
            return float(digits)
        except ValueError:
            return None

    @staticmethod
    def _format_zip_code(value: Optional[str]) -> Optional[str]:
        digits = re.sub(r"\D", "", value or "")
        if len(digits) != 8:
            return None
        return f"{digits[:5]}-{digits[5:]}"

    @staticmethod
    def _infer_property_type(title: str, property_features: list[str], condo_features: list[str]) -> str:
        fingerprint = " ".join([title, *property_features, *condo_features]).lower()
        if "condom" in fingerprint:
            return "casa"
        if "chácara" in fingerprint or "chacara" in fingerprint:
            return "chacara"
        if "fazenda" in fingerprint:
            return "fazenda"
        if "sítio" in fingerprint or "sitio" in fingerprint:
            return "sitio"
        if "terreno" in fingerprint or "lote" in fingerprint:
            return "terreno"
        return "casa"

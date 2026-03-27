"""
ImovelWeb Scraper
Scrapes property sale listings from ImovelWeb using Playwright DOM extraction.
"""
from __future__ import annotations

import html
import json
import random
import re
from typing import Any, Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class ImovelWebScraper(HTTPScraper):
    """Scraper for ImovelWeb sale listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="imovelweb",
                display_name="ImovelWeb",
                description="Scraper de imóveis à venda no Distrito Federal pelo ImovelWeb",
                category=ScrapingCategory.PROPERTIES,
                source_type=SourceType.HTTP,
                version="1.1.0",
            ),
            base_url="https://www.imovelweb.com.br",
            endpoint="/imoveis-venda-distrito-federal.html",
            enabled=True,
            timeout=20,
            rate_limit_delay=2.5,
            max_items_per_run=30,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_headless": False,
                "playwright_headful_fallback": True,
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3000,
            },
        )

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        seen: set[str] = set()
        for url in self._collect_listing_urls_with_playwright(self.config.get_full_url()):
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
        payload = self._extract_detail_payload_with_playwright(url)
        if not payload:
            return None
        return self._build_item_from_payload(url, payload)

    def _collect_listing_urls_with_playwright(self, url: str) -> list[str]:
        payload = self._playwright_extract(
            url=url,
            script="""
() => {
  return Array.from(document.querySelectorAll('a[href*="/propriedades/"]'))
    .map((anchor) => anchor.href)
    .filter(Boolean)
}
""",
        )
        if not isinstance(payload, list):
            return []

        urls: list[str] = []
        seen: set[str] = set()
        for raw_url in payload:
            normalized = self._normalize_listing_url(raw_url)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    def _extract_detail_payload_with_playwright(self, url: str) -> Optional[dict[str, Any]]:
        payload = self._playwright_extract(
            url=url,
            script="""
() => {
  const clean = (value) => {
    if (value === null || value === undefined) return null
    const text = String(value).replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim()
    return text || null
  }

  const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
    .map((script) => script.textContent || '')
    .filter(Boolean)

  const images = Array.from(document.querySelectorAll('img[src]'))
    .map((img) => img.src)
    .filter((src) => src && src.includes('imovelwebcdn.com'))

  const article = document.querySelector('article')

  return {
    final_url: window.location.href,
    page_title: document.title || null,
    title: clean(document.querySelector('h1')?.textContent),
    article_text: clean(article?.innerText),
    publisher: clean(document.querySelector('a[href*="/imobiliarias/"]')?.textContent),
    images,
    ldjson_scripts: scripts,
  }
}
""",
        )
        return payload if isinstance(payload, dict) else None

    def _build_item_from_payload(self, url: str, payload: dict[str, Any]) -> Optional[ScrapedItem]:
        article_text = self._normalize_multiline_text(payload.get("article_text"))
        schema = self._extract_house_schema(payload.get("ldjson_scripts"))
        page_title = self._normalize_text(payload.get("page_title"))
        title = self._normalize_text(payload.get("title")) or self._extract_title_from_page_title(page_title)
        description = self._extract_description(article_text, schema)
        images = self._normalize_image_list(payload.get("images"))
        publisher = self._normalize_text(payload.get("publisher"))

        full_title = self._normalize_text((schema or {}).get("name")) or page_title
        price = self._extract_price(article_text, full_title)
        condo_fee = self._extract_currency_value(article_text, r"Condom[ií]nio\s*R\$\s*([\d\.\,]+)")
        iptu = self._extract_currency_value(article_text, r"IPTU\s*R\$\s*([\d\.\,]+)")
        metrics = self._extract_metrics(article_text, schema)
        locality = self._extract_locality(page_title, description)
        phone = self._normalize_phone((schema or {}).get("telephone"))
        canonical = self._normalize_listing_url(payload.get("final_url")) or url

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "city": locality.get("city"),
            "state": locality.get("state"),
            "street": locality.get("street"),
            "images": images,
            "contact_name": publisher,
            "contact_phone": phone,
            "attributes": {
                "listing_type": "sale",
                "property_type": self._infer_property_type(title, full_title),
                "total_area_m2": metrics.get("total_area_m2"),
                "covered_area_m2": metrics.get("covered_area_m2"),
                "bedrooms": metrics.get("bedrooms"),
                "bathrooms": metrics.get("bathrooms"),
                "parking_spots": metrics.get("parking_spots"),
                "suites": metrics.get("suites"),
                "property_age_years": metrics.get("property_age_years"),
                "condo_fee": condo_fee,
                "iptu": iptu,
            },
        }
        return self.build_scraped_item(url=canonical, scraped_data=scraped_data)

    def _playwright_extract(self, url: str, script: str) -> Optional[Any]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            from pyvirtualdisplay import Display  # type: ignore
        except Exception as exc:
            self.logger.error("ImovelWeb Playwright dependencies unavailable: %s", exc)
            return None

        viewport_width, viewport_height = self._playwright_virtual_display_size()
        user_agent = random.choice(self._user_agent_pool())
        wait_until = self._playwright_wait_until()
        wait_after_load_ms = self._playwright_wait_after_load_ms()

        try:
            with Display(visible=False, size=(viewport_width, viewport_height), use_xauth=False):
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=False,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                            "--disable-gpu",
                            "--disable-software-rasterizer",
                            "--disable-features=VizDisplayCompositor",
                        ],
                    )
                    context = browser.new_context(
                        user_agent=user_agent,
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                        viewport={"width": viewport_width, "height": viewport_height},
                    )
                    page = context.new_page()
                    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                    page.goto(url, wait_until=wait_until, timeout=(self.config.timeout or 20) * 1000)
                    page.wait_for_timeout(wait_after_load_ms)
                    result = page.evaluate(script)
                    context.close()
                    browser.close()
                    return result
        except Exception as exc:
            self.logger.error("ImovelWeb Playwright extraction failed for %s: %s", url, exc)
            return None

    def _extract_house_schema(self, raw_scripts: Any) -> Optional[dict[str, Any]]:
        if not isinstance(raw_scripts, list):
            return None
        for raw in raw_scripts:
            if not isinstance(raw, str):
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") in {
                "House",
                "SingleFamilyResidence",
                "Residence",
                "Apartment",
            }:
                return payload
        return None

    def _extract_title_from_page_title(self, page_title: Optional[str]) -> Optional[str]:
        if not page_title:
            return None
        title = page_title.split(" - R$ ", 1)[0]
        title = re.sub(r"^.+?com \d+ Quartos,\s*", "", title, flags=re.I)
        return self._normalize_text(title)

    def _extract_description(self, article_text: Optional[str], schema: Optional[dict[str, Any]]) -> Optional[str]:
        parts: list[str] = []
        if article_text:
            match = re.search(
                r"(Casa de .*?)(?:Ler descri[cç][aã]o completa|Perguntas para a imobili[áa]ria|Saiba mais sobre este im[óo]vel)",
                article_text,
                re.I | re.S,
            )
            candidate = match.group(1) if match else article_text
            candidate = re.sub(r"^.*?(Casa de \d+ Quartos.*?)$", r"\1", candidate, flags=re.I | re.S)
            candidate = re.sub(r"Atendimento:.*$", "", candidate, flags=re.I | re.S).strip()
            normalized = self._normalize_multiline_text(candidate)
            if normalized:
                parts.append(normalized)

        schema_description = self._normalize_multiline_text((schema or {}).get("description"))
        if schema_description and schema_description not in parts:
            parts.append(schema_description)
        return "\n\n".join(parts) if parts else None

    def _extract_price(self, article_text: Optional[str], title_text: Optional[str]) -> Optional[float]:
        for source in [article_text, title_text]:
            value = self._extract_currency_value(source, r"venda\s*R\$\s*([\d\.\,]+)")
            if value is not None:
                return value
            value = self._extract_currency_value(source, r"R\$\s*([\d\.\,]+)")
            if value is not None:
                return value
        return None

    def _extract_currency_value(self, text: Optional[str], pattern: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(pattern, text, re.I)
        if not match:
            return None
        return self.parse_price(match.group(1))

    def _extract_metrics(self, article_text: Optional[str], schema: Optional[dict[str, Any]]) -> dict[str, Optional[float | int]]:
        text = article_text or ""
        return {
            "total_area_m2": self._extract_number(text, r"(\d+(?:[\.,]\d+)?)\s*m²\s*tot"),
            "covered_area_m2": self._extract_number(text, r"(\d+(?:[\.,]\d+)?)\s*m²\s*(?:útil|util)"),
            "bedrooms": self._extract_int(text, r"(\d+)\s+quartos?") or self._safe_int((schema or {}).get("numberOfBedrooms")),
            "bathrooms": self._extract_int(text, r"(\d+)\s+ban(?:heiros?|s?)") or self._safe_int((schema or {}).get("numberOfBathroomsTotal")),
            "parking_spots": self._extract_int(text, r"(\d+)\s+vagas?"),
            "suites": self._extract_int(text, r"(\d+)\s+su[ií]tes?"),
            "property_age_years": self._extract_int(text, r"(\d+)\s+anos?"),
        }

    def _extract_locality(self, page_title: Optional[str], description: Optional[str]) -> dict[str, Optional[str]]:
        city = None
        state = None
        street = None

        title_text = page_title or ""
        locality_match = re.search(r"Quarto(?:s)?\,\s*([^,-]+?)(?:,\s*([^,-]+?))?\s*-\s*R\$", title_text, re.I)
        if locality_match:
            city = self._normalize_text(locality_match.group(2) or locality_match.group(1))

        if "Distrito Federal" in title_text or re.search(r"\bDF\b", description or "", re.I):
            state = "DF"

        street_match = re.search(r"Localiza[cç][aã]o:\s*([^\.]+)", description or "", re.I)
        if street_match:
            street = self._normalize_text(street_match.group(1))
            if not state:
                state_match = re.search(r"\b([A-Z]{2})\b", street or "")
                if state_match:
                    state = self._normalize_state(state_match.group(1))
            if not city:
                city_match = re.search(r",\s*([^,-]+)(?:-[A-Z]{2})?$", street or "")
                if city_match:
                    city = self._normalize_text(city_match.group(1))

        return {"city": city, "state": state, "street": street}

    def _infer_property_type(self, title: Optional[str], full_title: Optional[str]) -> str:
        text = f"{title or ''} {full_title or ''}".lower()
        if "apartamento" in text:
            return "apartamento"
        if "kitnet" in text or "studio" in text:
            return "kitnet"
        if "terreno" in text:
            return "terreno"
        if "chácara" in text or "chacara" in text:
            return "chacara"
        if "fazenda" in text:
            return "fazenda"
        return "casa"

    def _normalize_listing_url(self, url: Any) -> Optional[str]:
        if not url:
            return None
        normalized = self._normalize_text(url)
        if not normalized:
            return None
        if normalized.startswith("/"):
            normalized = urljoin(self.config.base_url, normalized)
        normalized = normalized.split("?", 1)[0].rstrip("/")
        return normalized or None

    def _normalize_image_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        urls: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = self._normalize_text(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
        return urls

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value)).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _normalize_multiline_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = html.unescape(str(value)).replace("\xa0", " ").replace("\r", "\n").replace("\t", " ")
        text = re.sub(r"[ ]{2,}", " ", text)
        lines = [re.sub(r"\s+", " ", line).strip(" -:") for line in text.split("\n")]
        lines = [line for line in lines if line]
        return "\n".join(lines) or None

    @staticmethod
    def _normalize_phone(value: Any) -> Optional[str]:
        text = re.sub(r"\D+", "", str(value or ""))
        if len(text) < 10:
            return None
        if text.startswith("55") and len(text) > 11:
            text = text[2:]
        return text

    @staticmethod
    def _normalize_state(value: Any) -> Optional[str]:
        text = re.sub(r"[^A-Za-z]", "", str(value or "")).upper()
        return text[:2] if len(text) >= 2 else None

    @staticmethod
    def _extract_number(text: Optional[str], pattern: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(pattern, text, re.I)
        if not match:
            return None
        raw = match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _extract_int(text: Optional[str], pattern: str) -> Optional[int]:
        if not text:
            return None
        match = re.search(pattern, text, re.I)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

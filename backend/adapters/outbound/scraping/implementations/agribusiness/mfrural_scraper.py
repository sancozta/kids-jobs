"""
MF Rural Scraper
Scrapes agribusiness rural property listings from MF Rural.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class MFRuralScraper(HTTPScraper):
    """Scraper for MF Rural agribusiness listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="mfrural",
                display_name="MF Rural",
                description="Scraper de fazendas e imóveis rurais do MF Rural",
                category=ScrapingCategory.AGRIBUSINESS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.mfrural.com.br",
            endpoint="/produtos/1-7/fazendas-imoveis-rurais",
            enabled=True,
            rate_limit_delay=1.5,
            max_items_per_run=100,
            strategy=ScrapingStrategy.HTTP_ANTIBOT,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            self.logger.info("Scraping MF Rural list from: %s", self.config.get_full_url())
            detail_urls = self._collect_listing_urls()
            if not detail_urls:
                self.logger.warning("No MF Rural detail URLs found")
                return items

            for idx, detail_url in enumerate(detail_urls):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    detail_response = self.fetch_page(detail_url)
                    if not detail_response:
                        continue
                    item = self._parse_listing_detail(detail_url, detail_response.text)
                    if item:
                        items.append(item)
                except Exception as exc:
                    self.logger.error("Error parsing MF Rural detail %s: %s", detail_url, exc)

            self.logger.info("Scraped %s items from MF Rural", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping MF Rural: %s", exc)
            return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        detail_url = self._normalize_detail_url(url)
        if not detail_url:
            return None

        response = self.fetch_page(detail_url)
        if not response:
            return None
        return self._parse_listing_detail(detail_url, response.text)

    def _collect_listing_urls(self) -> list[str]:
        page_number = 1
        collected: list[str] = []
        seen: set[str] = set()

        while True:
            page_url = self._build_listing_page_url(page_number)
            response = self.fetch_page(page_url)
            if not response:
                break

            page_urls = self._extract_detail_urls_from_listing_html(response.text)
            if not page_urls:
                break

            new_urls = 0
            for detail_url in page_urls:
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                collected.append(detail_url)
                new_urls += 1
                if self.config.max_items_per_run and len(collected) >= self.config.max_items_per_run:
                    return collected

            next_page_url = self._extract_next_page_url(response.text)
            if not next_page_url or new_urls == 0:
                break
            page_number += 1

        return collected

    def _build_listing_page_url(self, page_number: int) -> str:
        base_url = self.config.get_full_url()
        if page_number <= 1:
            return base_url
        return f"{base_url}?pg={page_number}"

    def _extract_detail_urls_from_listing_html(self, html: str) -> list[str]:
        soup = self.parse_html(html)
        urls: list[str] = []

        for anchor in soup.select("a[href*='/detalhe/']"):
            href = anchor.get("href", "")
            normalized = self._normalize_detail_url(href)
            if normalized:
                urls.append(normalized)

        unique: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            unique.append(url)
        return unique

    def _extract_next_page_url(self, html: str) -> Optional[str]:
        soup = self.parse_html(html)
        for anchor in soup.select("a[href]"):
            text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
            if text != "próxima" and text != "proxima":
                continue
            return self._normalize_listing_page_url(anchor.get("href", ""))
        return None

    def _normalize_listing_page_url(self, href: str) -> Optional[str]:
        cleaned = (href or "").strip()
        if not cleaned:
            return None
        absolute = cleaned if cleaned.startswith("http") else urljoin(self.config.base_url, cleaned)
        return absolute.split("#", 1)[0]

    def _normalize_detail_url(self, href: str) -> Optional[str]:
        cleaned = (href or "").strip()
        if not cleaned:
            return None
        absolute = cleaned if cleaned.startswith("http") else urljoin(self.config.base_url, cleaned)
        absolute = absolute.split("#", 1)[0].split("?", 1)[0]
        if "/detalhe/" not in absolute:
            return None
        return absolute

    def _parse_listing_detail(self, detail_url: str, html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(html)
        page_text = " ".join(soup.get_text(" ", strip=True).split())

        title = self._extract_title(soup, detail_url)
        description = self._extract_description(soup)
        price = self._extract_price(soup, page_text)
        city, state = self._extract_city_state(soup, title, page_text)
        area_hectares = self._extract_area_hectares(title, description or page_text)
        images = self._extract_images(html)
        listing_type = "sale"
        irrigation = self._extract_irrigation(description or page_text)

        attributes: dict = {"listing_type": listing_type}
        if area_hectares is not None:
            attributes["area_hectares"] = area_hectares
        if irrigation is not None:
            attributes["irrigation"] = irrigation

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "BRL",
            "city": city,
            "state": state,
            "images": images,
            "attributes": attributes,
        }
        return self.build_scraped_item(url=detail_url, scraped_data=scraped_data)

    def _extract_title(self, soup, detail_url: str) -> Optional[str]:
        for h1 in soup.select("h1"):
            title = " ".join(h1.get_text(" ", strip=True).split()).strip()
            if title:
                return title
        og_title = soup.select_one("meta[property='og:title']")
        if og_title and og_title.get("content"):
            title = " ".join(og_title.get("content", "").split()).strip()
            if title:
                return title
        slug = detail_url.rstrip("/").split("/")[-1]
        return slug.replace("-", " ").title().strip() if slug else None

    def _extract_description(self, soup) -> Optional[str]:
        description_block = soup.select_one(".descricao")
        if description_block:
            text = " ".join(description_block.get_text(" ", strip=True).split())
            text = re.sub(r"^Descrição\s*", "", text, flags=re.IGNORECASE).strip()
            if text:
                return text

        meta_description = soup.select_one("meta[name='description']")
        if meta_description and meta_description.get("content"):
            return " ".join(meta_description.get("content", "").split()).strip() or None
        return None

    def _extract_price(self, soup, page_text: str) -> Optional[float]:
        for selector in [
            ".preco-produto__item__preco__cheio__desconto",
            ".preco-produto__item__preco__cheio",
            ".preco-produto__container strong",
            ".preco-produto__item__wrap strong",
            ".preco-produto .preco-produto__item span",
            ".preco-produto",
            ".valor",
            ".preco",
        ]:
            candidate = self.extract_text(soup, selector)
            price = self.parse_price(candidate)
            if price is not None:
                return price

        investment_match = re.search(
            r"VALOR\s+DO\s+INVESTIMENTO[:\s]*R\$\s*([\d\.\,]+)",
            page_text,
            flags=re.IGNORECASE,
        )
        if investment_match:
            return self.parse_price(f"R$ {investment_match.group(1)}")

        price_matches = re.findall(r"R\$\s*[\d\.\,]+", page_text, flags=re.IGNORECASE)
        if not price_matches:
            return None

        for candidate in reversed(price_matches):
            price = self.parse_price(candidate)
            if price is not None:
                return price
        return None

    def _extract_city_state(self, soup, title: Optional[str], page_text: str) -> tuple[Optional[str], Optional[str]]:
        location_text = self.extract_text(soup, ".tipo-cidade p, .tipo-cidade")
        for text in [location_text, title, page_text]:
            city, state = self._extract_city_state_from_text(text)
            if city or state:
                return city, state
        return None, None

    def _extract_city_state_from_text(self, text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None
        normalized = " ".join(text.split()).strip()

        slash_match = re.search(r"([A-Za-zÀ-ÿ' -]+?)/([A-Z]{2})\b", normalized)
        if slash_match:
            city = " ".join(slash_match.group(1).split()).strip(" -/")
            state = slash_match.group(2).upper()
            return city or None, state

        hyphen_match = re.search(r"\bem\s+(.+?)\s*-\s*([A-Z]{2})\b", normalized, flags=re.IGNORECASE)
        if hyphen_match:
            city = " ".join(hyphen_match.group(1).split()).strip(" -/")
            state = hyphen_match.group(2).upper()
            return city or None, state

        return None, None

    def _extract_area_hectares(self, title: Optional[str], text: str) -> Optional[float]:
        for source_text in [title or "", text]:
            match = re.search(r"([\d\.\,]+)\s*Hectares?\b", source_text, flags=re.IGNORECASE)
            if match:
                parsed = self._parse_numeric_token(match.group(1))
                if parsed is not None:
                    return parsed
            match = re.search(r"([\d\.\,]+)\s*ha\b", source_text, flags=re.IGNORECASE)
            if match:
                parsed = self._parse_numeric_token(match.group(1))
                if parsed is not None:
                    return parsed
        return None

    def _extract_images(self, html: str) -> list[str]:
        urls = re.findall(
            r"https://img\.mfrural\.com\.br/api/image\?url=https://s3\.amazonaws\.com/mfrural-produtos-us/[^\s\"']+\.(?:jpg|jpeg|png|webp)(?:&[^\s\"']+)?",
            html,
            flags=re.IGNORECASE,
        )

        best_by_asset: dict[str, str] = {}
        best_score: dict[str, int] = {}
        for url in urls:
            asset_match = re.search(r"url=(https://s3\.amazonaws\.com/mfrural-produtos-us/[^\s&]+)", url, flags=re.IGNORECASE)
            asset_key = asset_match.group(1) if asset_match else url
            width_match = re.search(r"[?&]width=(\d+)", url, flags=re.IGNORECASE)
            width = int(width_match.group(1)) if width_match else 0
            if width and width < 200:
                continue

            score = width
            current_score = best_score.get(asset_key, -1)
            if score < current_score:
                continue
            best_score[asset_key] = score
            best_by_asset[asset_key] = url

        unique: list[str] = []
        seen: set[str] = set()
        for url in best_by_asset.values():
            if url in seen:
                continue
            seen.add(url)
            unique.append(url)
        return unique

    def _extract_irrigation(self, text: str) -> Optional[bool]:
        normalized = text.lower()
        if "irrigação" in normalized or "irrigacao" in normalized:
            return True
        return None

    @staticmethod
    def _parse_numeric_token(value: str) -> Optional[float]:
        raw = (value or "").strip()
        if not raw:
            return None
        if "," in raw and "." in raw:
            normalized = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            normalized = raw.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
            normalized = raw.replace(".", "")
        else:
            normalized = raw
        try:
            return float(normalized)
        except ValueError:
            return None

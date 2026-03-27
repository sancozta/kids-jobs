"""
Tractian Scraper
Scrapes remote back-end engineering roles from Tractian careers.
"""
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class TractianScraper(HTTPScraper):
    """Scraper for Tractian careers job listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="tractian",
                display_name="Tractian Careers",
                description="Scraper de vagas remotas do time Back-End Engineering da Tractian",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://careers.tractian.com",
            endpoint="/jobs?workType=remote&team=Back-End+Engineering",
            enabled=True,
            rate_limit_delay=2.5,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        detail_response = self.fetch_page(url)
        if not detail_response:
            return None
        detail_soup = self.parse_html(detail_response.text)
        return self._parse_detail(url=url, listing=None, detail_soup=detail_soup, raw_html=detail_response.text)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            url = self.config.get_full_url()
            self.logger.info("Scraping Tractian from: %s", url)
            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select("a[href^='/jobs/']")
            seen_urls: set[str] = set()

            for listing in listings:
                if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                    break

                item = self._parse_listing(listing)
                if not item or item.url in seen_urls:
                    continue

                seen_urls.add(item.url)
                items.append(item)

            self.logger.info("Scraped %s items from Tractian", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping Tractian: %s", exc)
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        href = listing.get("href", "").strip()
        if not href or href == "/jobs":
            return None

        url = urljoin(self.config.base_url, href)
        title = self.extract_text(listing, "h2")
        if not title:
            return None

        detail_response = self.fetch_page(url)
        if not detail_response:
            return None

        detail_soup = self.parse_html(detail_response.text)
        return self._parse_detail(url=url, listing=listing, detail_soup=detail_soup, raw_html=detail_response.text)

    def _parse_detail(self, *, url: str, listing, detail_soup, raw_html: str) -> Optional[ScrapedItem]:
        title = self.extract_text(detail_soup, "main h1") or (self.extract_text(listing, "h2") if listing else None)
        listing_parts = [part.get_text(" ", strip=True) for part in listing.select("p span")] if listing else []
        location_text = " / ".join(part for part in listing_parts if part) or self._search_json_value(raw_html, "addressLocality") or ""
        department = listing_parts[0] if len(listing_parts) >= 1 else "Software Development"
        team = listing_parts[1] if len(listing_parts) >= 2 else "Back-End Engineering"
        city, state = self._extract_city_state(raw_html, location_text)
        description = self._extract_description(detail_soup)
        employment_type = self._search_json_value(raw_html, "employmentType")
        date_posted = self._search_json_value(raw_html, "datePosted")

        scraped_data = {
            "title": title,
            "description": description,
            "currency": "BRL",
            "city": city,
            "state": state,
            "zip_code": self._search_json_value(raw_html, "postalCode"),
            "street": self._search_json_value(raw_html, "streetAddress"),
            "attributes": {
                "company": self._search_json_value(raw_html, "name") or "Tractian",
                "salary_text": None,
                "seniority": self._infer_seniority(title or description or ""),
                "contract_type": self._infer_contract_type(employment_type),
                "work_model": "remoto" if "remote" in location_text.lower() else None,
                "experience_years": self._extract_experience_years(description),
            },
            "links": [self._search_json_value(raw_html, "applicationUrl")] if self._search_json_value(raw_html, "applicationUrl") else [],
        }

        # Team/department are useful context but not part of the canonical jobs schema.
        if department or team:
            extra_description = " ".join(part for part in [department, team] if part)
            if extra_description and extra_description.lower() not in (description or "").lower():
                scraped_data["description"] = f"{extra_description}. {description}" if description else extra_description

        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_description(detail_soup) -> Optional[str]:
        blocks: list[str] = []
        for selector in ("article[data-cid='job-description']", "div.bg-slate-100 article", "div.bg-slate-100 section"):
            for node in detail_soup.select(selector):
                text = " ".join(node.get_text(" ", strip=True).split())
                if text and text not in blocks:
                    blocks.append(text)
        return " ".join(blocks) or None

    @staticmethod
    def _search_json_value(raw_html: str, key: str) -> Optional[str]:
        patterns = [
            rf'"{re.escape(key)}"\s*:\s*"([^"]+)"',
            rf'\\"{re.escape(key)}\\"\s*:\s*\\"([^"]+)\\"',
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_html)
            if match:
                return match.group(1).strip()
        return None

    def _extract_city_state(self, raw_html: str, fallback: str) -> tuple[Optional[str], Optional[str]]:
        city = self._search_json_value(raw_html, "addressLocality")
        state = self._search_json_value(raw_html, "addressRegion")
        if city or state:
            return city, state

        match = re.search(r"([A-Za-zÀ-ÿ\s]+),\s*([A-Z]{2})", fallback)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|staff|principal|lead|manager)\b", normalized):
            return "senior"
        if re.search(r"\b(pleno|mid)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|jr)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(employment_type: Optional[str]) -> Optional[str]:
        normalized = (employment_type or "").lower()
        if normalized in {"full_time", "full-time", "full time"}:
            return "clt"
        if normalized in {"contract", "contractor"}:
            return "pj"
        if "freelance" in normalized:
            return "freelancer"
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s+years", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

"""
Wellfound Scraper
Scrapes remote software engineer jobs from Wellfound.
"""
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import Tag

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class WellfoundScraper(HTTPScraper):
    """Scraper for Wellfound remote software engineer roles."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="wellfound",
                display_name="Wellfound",
                description="Scraper de vagas remotas de software engineer do Wellfound",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://wellfound.com",
            endpoint="/role/r/software-engineer",
            enabled=True,
            timeout=45,
            rate_limit_delay=2.0,
            max_items_per_run=20,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3200,
                "playwright_headful_fallback": True,
                "playwright_virtual_display_size": "1440x960",
                "playwright_block_resource_types": ["image", "media", "font"],
                "playwright_retry_count": 2,
                "playwright_retry_delay_ms": 1200,
            },
        )

    def scrape(self) -> list[ScrapedItem]:
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return []

        soup = self.parse_html(response.text)
        items: list[ScrapedItem] = []
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href^='/jobs/']"):
            href = (anchor.get("href") or "").strip()
            if not re.match(r"^/jobs/\d+", href):
                continue
            url = urljoin(self.config.base_url, href).split("?", 1)[0]
            if url in seen_urls:
                continue
            seen_urls.add(url)
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

        soup = self.parse_html(response.text)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        title = self.extract_text(soup, "h1")
        if not title:
            return None

        company = self._extract_company(soup)
        salary_text = self._extract_salary_text(soup)
        price = self._extract_salary_value(salary_text)
        location_text = self._extract_location_text(soup)
        work_model = "remoto" if "remote" in (location_text or "").lower() else None
        description = self._extract_description(soup)

        scraped_data = {
            "title": title,
            "description": description,
            "price": price,
            "currency": "USD",
            "city": "Remote" if work_model == "remoto" else None,
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(" ".join(filter(None, [title, description]))),
                "contract_type": self._infer_contract_type(" ".join(filter(None, [location_text, description, page_text]))),
                "work_model": work_model,
                "experience_years": self._extract_experience_years(description),
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _extract_company(soup) -> Optional[str]:
        about_header = soup.find(re.compile(r"^h[23]$"), string=re.compile(r"About the company", re.I))
        if about_header:
            company_link = about_header.find_next("a", href=re.compile(r"^/company/"))
            if company_link:
                return " ".join(company_link.get_text(" ", strip=True).split())
        header_company = soup.find("a", href=re.compile(r"^/company/"))
        if header_company:
            return " ".join(header_company.get_text(" ", strip=True).split())
        return None

    @staticmethod
    def _extract_salary_text(soup) -> Optional[str]:
        text = " ".join(soup.get_text(" ", strip=True).split())
        match = re.search(r"\$\d+[kK]?\s*[–-]\s*\$\d+[kK]?", text)
        return match.group(0) if match else None

    def _extract_salary_value(self, salary_text: Optional[str]) -> Optional[float]:
        if not salary_text:
            return None
        normalized = salary_text.lower().replace("$", "").replace(" ", "")
        first = re.split(r"[–-]", normalized)[0]
        multiplier = 1000.0 if first.endswith("k") else 1.0
        try:
            return float(first.rstrip("k")) * multiplier
        except ValueError:
            return None

    @staticmethod
    def _extract_location_text(soup) -> Optional[str]:
        title = soup.find("h1")
        if not title:
            return None
        list_node = title.find_next("ul")
        if not list_node:
            return None
        text = " ".join(list_node.get_text(" ", strip=True).split())
        location_match = re.search(r"Remote\s*\([^)]+\)|Remote|Onsite\s*\([^)]+\)|Hybrid\s*\([^)]+\)", text, re.I)
        return location_match.group(0) if location_match else None

    @staticmethod
    def _extract_description(soup) -> Optional[str]:
        start = soup.find(re.compile(r"^h[23]$"), string=re.compile(r"About the job", re.I))
        if not start:
            return None
        blocks: list[str] = []
        for sibling in start.find_next_siblings():
            if isinstance(sibling, Tag) and sibling.name in {"h2", "h3"}:
                heading_text = " ".join(sibling.get_text(" ", strip=True).split())
                if re.search(r"About the company", heading_text, re.I):
                    break
            text = " ".join(sibling.get_text(" ", strip=True).split())
            if text:
                blocks.append(text)
        return "\n\n".join(blocks) or None

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|sr|staff|principal|lead)\b", normalized):
            return "senior"
        if re.search(r"\b(mid|intermediate|pleno)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|jr|new grad|entry)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(text: str) -> Optional[str]:
        normalized = text.lower()
        if "contract" in normalized or "freelance" in normalized:
            return "pj"
        if "full time" in normalized or "full-time" in normalized:
            return "clt"
        if "part time" in normalized or "part-time" in normalized:
            return "temporario"
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s+(?:years|yrs)", text, re.IGNORECASE)
        if range_match:
            return int(range_match.group(1))
        match = re.search(r"(\d+)(?:\+)?\s+(?:years|yrs)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

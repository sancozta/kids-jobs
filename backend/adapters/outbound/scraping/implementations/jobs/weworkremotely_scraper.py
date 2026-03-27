"""
We Work Remotely Scraper
Scrapes remote programming jobs from We Work Remotely RSS feed.
"""
import html
import re
import xml.etree.ElementTree as ET
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class WeWorkRemotelyScraper(HTTPScraper):
    """Scraper for We Work Remotely programming jobs."""

    ALLOWED_CATEGORIES = {
        "back-end programming",
        "front-end programming",
        "full-stack programming",
        "devops and sysadmin",
        "programming",
    }

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="weworkremotely",
                display_name="We Work Remotely",
                description="Scraper de vagas remotas de programação do We Work Remotely",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.RSS,
                version="1.0.0",
            ),
            base_url="https://weworkremotely.com",
            endpoint="/categories/remote-programming-jobs.rss",
            enabled=True,
            timeout=30,
            rate_limit_delay=1.5,
            max_items_per_run=50,
        )

    def scrape(self) -> list[ScrapedItem]:
        feed = self._load_feed_items()
        items: list[ScrapedItem] = []
        for entry in feed:
            item = self._build_item_from_entry(entry)
            if item:
                items.append(item)
            if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                break
        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_target = self._normalize_scrape_url(url)
        for entry in self._load_feed_items():
            entry_url = self._normalize_scrape_url(entry.get("link"))
            if entry_url == normalized_target:
                return self._build_item_from_entry(entry)
        return None

    def _load_feed_items(self) -> list[dict]:
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return []
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return []
        items: list[dict] = []
        for node in root.findall("./channel/item"):
            entry = {
                "title": node.findtext("title"),
                "link": node.findtext("link"),
                "category": node.findtext("category"),
                "pub_date": node.findtext("pubDate"),
                "region": node.findtext("region"),
                "description": node.findtext("description"),
            }
            items.append(entry)
        return items

    def _build_item_from_entry(self, entry: dict) -> Optional[ScrapedItem]:
        category = self._normalize_text(entry.get("category"))
        if category and category.lower() not in self.ALLOWED_CATEGORIES:
            return None

        title_text = self._normalize_text(entry.get("title"))
        if not title_text or ":" not in title_text:
            return None
        company, title = [part.strip() for part in title_text.split(":", 1)]
        description = self._html_to_text(entry.get("description"))
        if not self._is_tech_job(" ".join(filter(None, [title, category, description]))):
            return None

        salary_text = self._extract_salary_text(description)
        salary_value = self.parse_price(salary_text) if salary_text else None
        region = self._normalize_text(entry.get("region"))
        city = "Remote" if region else None

        scraped_data = {
            "title": title,
            "description": description,
            "price": salary_value,
            "currency": "USD",
            "city": city,
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(" ".join(filter(None, [title, description]))),
                "contract_type": self._infer_contract_type(description or ""),
                "work_model": "remoto",
                "experience_years": self._extract_experience_years(description),
            },
        }
        return self.build_scraped_item(url=entry["link"], scraped_data=scraped_data)

    @staticmethod
    def _normalize_text(value) -> Optional[str]:
        if value is None:
            return None
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        return normalized or None

    @staticmethod
    def _html_to_text(value) -> Optional[str]:
        if not value:
            return None
        text = html.unescape(str(value))
        text = re.sub(r"<br\\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"</p>", "\n\n", text, flags=re.I)
        text = re.sub(r"</li>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"\s+\n", "\n", text)
        text = re.sub(r"\n\s+", "\n", text)
        return text.strip() or None

    @staticmethod
    def _is_tech_job(text: str) -> bool:
        normalized = (text or "").lower()
        return any(
            keyword in normalized
            for keyword in (
                "developer",
                "engineer",
                "software",
                "python",
                "java",
                "javascript",
                "typescript",
                "backend",
                "frontend",
                "full-stack",
                "full stack",
                "react",
                "angular",
                "golang",
                "ruby",
                "devops",
            )
        )

    @staticmethod
    def _extract_salary_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        match = re.search(r"\$\s?[\d,]+(?:k|K)?(?:\s*[–-]\s*\$\s?[\d,]+(?:k|K)?)?", text)
        if match:
            return match.group(0)
        return None

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|sr|staff|principal|lead)\b", normalized):
            return "senior"
        if re.search(r"\b(mid|intermediate|pleno)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|jr|entry)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(text: str) -> Optional[str]:
        normalized = (text or "").lower()
        if "contract" in normalized or "freelance" in normalized:
            return "pj"
        if "full-time" in normalized or "full time" in normalized:
            return "clt"
        if "part-time" in normalized:
            return "temporario"
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s+years", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

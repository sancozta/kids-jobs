"""
RemoteOK Scraper
Scrapes remote development jobs from RemoteOK JSON feed.
"""
import html
import json
import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class RemoteOKScraper(HTTPScraper):
    """Scraper for RemoteOK development jobs."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="remoteok",
                display_name="RemoteOK",
                description="Scraper de vagas remotas de desenvolvimento do RemoteOK",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.API,
                version="1.0.0",
            ),
            base_url="https://remoteok.com",
            endpoint="/remote-dev-jobs.json",
            enabled=True,
            timeout=30,
            rate_limit_delay=1.5,
            max_items_per_run=50,
        )

    def scrape(self) -> list[ScrapedItem]:
        payload = self._load_payload()
        items: list[ScrapedItem] = []
        for entry in payload:
            item = self._build_item_from_entry(entry)
            if item:
                items.append(item)
            if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                break
        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized_target = self._normalize_scrape_url(url)
        for entry in self._load_payload():
            entry_url = self._normalize_scrape_url(entry.get("url"))
            if entry_url == normalized_target:
                return self._build_item_from_entry(entry)
        return None

    def _load_payload(self) -> list[dict]:
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return []
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [entry for entry in payload if isinstance(entry, dict) and entry.get("id")]

    def _build_item_from_entry(self, entry: dict) -> Optional[ScrapedItem]:
        title = self._normalize_text(entry.get("position"))
        url = self._normalize_text(entry.get("url"))
        if not title or not url:
            return None

        description = self._html_to_text(entry.get("description"))
        combined_text = " ".join(
            filter(
                None,
                [
                    title,
                    self._normalize_text(entry.get("company")),
                    description,
                    " ".join(entry.get("tags") or []),
                ],
            )
        )
        if not self._is_tech_job(combined_text):
            return None

        salary_min = entry.get("salary_min")
        salary_max = entry.get("salary_max")
        salary_text = None
        if salary_min or salary_max:
            salary_text = f"${int(salary_min or 0):,} - ${int(salary_max or 0):,}".replace(",0", "")

        location_text = self._normalize_text(entry.get("location"))
        city = "Remote" if not location_text else location_text

        scraped_data = {
            "title": title,
            "description": description,
            "price": float(salary_min) if isinstance(salary_min, (int, float)) and salary_min > 0 else None,
            "currency": "USD",
            "city": city,
            "attributes": {
                "company": self._normalize_text(entry.get("company")),
                "salary_text": salary_text,
                "seniority": self._infer_seniority(combined_text),
                "contract_type": self._infer_contract_type(description or ""),
                "work_model": "remoto",
                "experience_years": self._extract_experience_years(description),
            },
            "links": [self._normalize_text(entry.get("apply_url"))] if entry.get("apply_url") else [],
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

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
                "fullstack",
                "full-stack",
                "react",
                "angular",
                "golang",
                "ruby",
                "devops",
                "data",
                "cloud",
                "qa",
            )
        )

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
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s+years", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

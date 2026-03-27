"""
VanHack Scraper
Scrapes remote jobs from VanHack through hydrated list pages and detail pages.
"""
import html
import json
import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class VanHackScraper(HTTPScraper):
    """Scraper for VanHack remote job listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="vanhack",
                display_name="VanHack",
                description="Scraper de vagas remotas internacionais da VanHack",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://vanhack.com",
            endpoint="/jobs/remote-jobs-in-united_states",
            enabled=True,
            timeout=45,
            rate_limit_delay=2.5,
            max_items_per_run=50,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3500,
                "playwright_headful_fallback": True,
                "playwright_virtual_display_size": "1440x960",
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        return self._parse_job_from_detail(url)

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            url = self.config.get_full_url()
            self.logger.info("Scraping VanHack from: %s", url)

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            job_links = self._extract_job_links(soup)
            for idx, job_url in enumerate(job_links):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                item = self._parse_job_from_detail(job_url)
                if item:
                    items.append(item)

            self.logger.info("Scraped %s items from VanHack", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping VanHack: %s", exc)
            return items

    def _extract_job_links(self, soup) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        for anchor in soup.select('a[href*="/job/"]'):
            href = self._normalize_text(anchor.get("href"))
            if not href:
                continue
            full_url = href if href.startswith("http") else f"{self.config.base_url.rstrip('/')}/{href.lstrip('/')}"
            normalized_url = full_url.split("?", 1)[0]
            if normalized_url in seen:
                continue
            seen.add(normalized_url)
            links.append(normalized_url)
        return links

    def _parse_job_from_detail(self, url: str) -> Optional[ScrapedItem]:
        response = self.fetch_page(url)
        if not response:
            return None

        soup = self.parse_html(response.text)
        title = self._extract_title(soup) or "VanHack Job"
        description = self._extract_description(soup)
        hiring_org = self._extract_company(soup)
        location_text = self._extract_location_text(soup)
        city, state = self._parse_location(location_text)
        salary_text = self._extract_salary_text(soup)
        salary_currency = self._extract_salary_currency(salary_text) or "USD"
        salary = self._extract_salary_from_text(salary_text)
        employment_type = self._extract_employment_type(soup, description)
        application_url = self._extract_canonical_url(soup) or url

        scraped_data = {
            "title": title,
            "description": description,
            "price": salary,
            "currency": salary_currency,
            "city": city,
            "state": state,
            "links": [application_url] if application_url else [],
            "attributes": {
                "company": hiring_org,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(" ".join(filter(None, [title, description]))),
                "contract_type": self._infer_contract_type(employment_type),
                "work_model": "remoto",
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_title(self, soup) -> Optional[str]:
        meta_title = soup.select_one('meta[property="og:title"]')
        if meta_title and meta_title.get("content"):
            title = re.sub(r"\s+-\s+VanHack$", "", meta_title["content"]).strip()
            if title:
                return title
        header = soup.select_one("#vh-job-details-header-section")
        if not header:
            return None
        title_node = header.find_all("p")
        if len(title_node) >= 2:
            return self._normalize_text(title_node[1].get_text(" ", strip=True))
        return None

    def _extract_description(self, soup) -> Optional[str]:
        description_container = soup.select_one("#vh-job-details-job-about-section .sc-eQsaeD")
        if description_container:
            text = description_container.get_text("\n", strip=True)
            text = html.unescape(text)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n+", "\n\n", text)
            text = re.sub(r"\s+\n", "\n", text)
            text = re.sub(r"\n\s+", "\n", text)
            normalized = text.strip()
            if normalized:
                return normalized

        meta_description = soup.select_one('meta[property="og:description"]')
        if meta_description and meta_description.get("content"):
            return self._normalize_text(meta_description["content"])
        return None

    def _extract_company(self, soup) -> Optional[str]:
        description_container = soup.select_one("#vh-job-details-job-about-section .sc-eQsaeD strong")
        if description_container:
            return self._normalize_text(description_container.get_text(" ", strip=True))
        return "VanHack"

    def _extract_location_text(self, soup) -> Optional[str]:
        header = soup.select_one("#vh-job-details-header-section")
        if not header:
            return None
        for paragraph in header.select("p"):
            text = self._normalize_text(paragraph.get_text(" ", strip=True))
            if not text or text.lower().startswith("posted "):
                continue
            if "United States" in text:
                return text
            if re.fullmatch(r"[A-Za-zÀ-ÿ\s]+,\s*[A-Z]{2}", text):
                return text
        return None

    @staticmethod
    def _parse_location(location_text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not location_text:
            return None, None
        parts = [part.strip() for part in re.split(r",|-", location_text) if part.strip()]
        if not parts:
            return None, None
        city = parts[0]
        state = parts[1] if len(parts) > 1 and len(parts[1]) <= 3 else None
        if city.lower() == "remote":
            city = "Remote"
        return city, state

    def _extract_salary_text(self, soup) -> Optional[str]:
        header = soup.select_one("#vh-job-details-header-section")
        if not header:
            return None
        match = re.search(r"\$[\d,]+(?:\s+up to\s+\$[\d,]+)?\s+[A-Z]{3}/[A-Za-z]+", header.get_text(" ", strip=True))
        return self._normalize_text(match.group(0)) if match else None

    @staticmethod
    def _extract_salary_currency(salary_text: Optional[str]) -> Optional[str]:
        if not salary_text:
            return None
        match = re.search(r"\b([A-Z]{3})/", salary_text)
        return match.group(1) if match else None

    def _extract_salary_from_text(self, salary_text: Optional[str]) -> Optional[float]:
        if not salary_text:
            return None
        numbers = re.findall(r"\$([\d,]+)", salary_text)
        if not numbers:
            return None
        first_value = numbers[0].replace(",", "")
        try:
            return float(first_value)
        except ValueError:
            return None

    def _extract_employment_type(self, soup, description: Optional[str]) -> Optional[str]:
        page_text = soup.get_text(" ", strip=True)
        combined = " ".join(filter(None, [page_text, description]))
        if re.search(r"\bcontract\b", combined, re.IGNORECASE):
            return "Contract"
        if re.search(r"\bfull[- ]time\b", combined, re.IGNORECASE):
            return "Full-time"
        return None

    @staticmethod
    def _extract_canonical_url(soup) -> Optional[str]:
        canonical = soup.select_one('meta[property="og:url"]')
        if canonical and canonical.get("content"):
            return canonical["content"].strip()
        return None

    @staticmethod
    def _normalize_text(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get("name") or value.get("@id") or value.get("value")
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        return normalized or None

    @staticmethod
    def _normalize_state(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = str(value).strip()
        return None if normalized.lower() == "remote" else normalized

    @staticmethod
    def _extract_salary(base_salary) -> Optional[float]:
        if not isinstance(base_salary, dict):
            return None
        value = base_salary.get("value")
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _salary_text(base_salary, currency: str) -> Optional[str]:
        value = VanHackScraper._extract_salary(base_salary)
        if value is None:
            return None
        unit = None
        if isinstance(base_salary, dict):
            raw_value = base_salary.get("value")
            if isinstance(raw_value, dict):
                unit = raw_value.get("unitText")
        return f"{currency} {value:.0f}{f' / {unit}' if unit else ''}"

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|staff|principal|lead)\b", normalized):
            return "senior"
        if re.search(r"\b(mid|pleno)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|jr)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(employment_type: Optional[str]) -> Optional[str]:
        normalized = (employment_type or "").lower()
        if "contract" in normalized:
            return "pj"
        if "full-time" in normalized or "full time" in normalized:
            return "clt"
        if "part-time" in normalized or "part time" in normalized:
            return "clt"
        if "freelance" in normalized:
            return "freelancer"
        return None

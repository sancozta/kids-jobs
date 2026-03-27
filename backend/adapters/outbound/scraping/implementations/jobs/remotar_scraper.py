"""
Remotar Scraper
Scrapes remote tech jobs from Remotar.
"""
import html
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class RemotarScraper(HTTPScraper):
    """Scraper for Remotar job listings."""

    TECH_KEYWORDS = (
        "desenvolvedor",
        "developer",
        "engenheiro",
        "engineer",
        "software",
        "fullstack",
        "full-stack",
        "backend",
        "back-end",
        "frontend",
        "front-end",
        "mobile",
        "react",
        "angular",
        "java",
        "python",
        "node",
        "php",
        "golang",
        "go ",
        "ruby",
        "qa",
        "quality assurance",
        "devops",
        "sre",
        "cloud",
        "dados",
        "data",
        "machine learning",
        "ml",
        "ai",
        "arquiteto",
        "architect",
        "scrum",
        "tech",
        "ti",
    )

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="remotar",
                display_name="Remotar",
                description="Scraper de vagas remotas de TI e desenvolvimento da Remotar",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://remotar.com.br",
            endpoint="/",
            enabled=True,
            timeout=45,
            rate_limit_delay=2.0,
            max_items_per_run=25,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 3500,
                "playwright_headful_fallback": True,
                "playwright_virtual_display_size": "1440x960",
                "playwright_block_resource_types": ["image", "media", "font"],
                "playwright_retry_count": 2,
                "playwright_retry_delay_ms": 1200,
            },
        )

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        response = self.fetch_page(self.config.get_full_url())
        if not response:
            return items

        soup = self.parse_html(response.text)
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href^='/job/']"):
            href = (anchor.get("href") or "").strip()
            if not href:
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
        return self._parse_detail_page(url, response.text)

    def _parse_detail_page(self, url: str, raw_html: str) -> Optional[ScrapedItem]:
        job_data = self._extract_job_data(raw_html)
        if not job_data:
            return None

        title = self._normalize_text(job_data.get("title"))
        subtitle = self._normalize_text(job_data.get("subtitle"))
        description = self._build_description(job_data)
        company = self._extract_company(job_data)
        tags_text = self._extract_job_tags_text(job_data)
        combined_text = " ".join(
            part for part in [title, subtitle, description, company, tags_text] if part
        )
        if not self._is_tech_job(combined_text):
            return None

        salary_text = self._extract_salary_text(job_data.get("jobSalary"))
        salary_value = self._extract_salary_value(job_data.get("jobSalary"))
        work_model = "remoto" if str(job_data.get("type", "")).lower() == "remote" else None
        city, state = self._extract_city_state(job_data)
        location_hints = []
        country = job_data.get("country") or {}
        if isinstance(country, dict):
            country_name = self._normalize_text(country.get("name"))
            if country_name:
                location_hints.append(country_name)
        if subtitle:
            location_hints.append(subtitle)
        location_hint = " ".join(location_hints)

        scraped_data = {
            "title": title,
            "description": description or subtitle,
            "price": salary_value,
            "currency": "BRL",
            "city": city,
            "state": state,
            "links": [job_data.get("externalLink")] if job_data.get("externalLink") else [],
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(" ".join(filter(None, [title, subtitle, description, tags_text]))),
                "contract_type": self._infer_contract_type(" ".join(filter(None, [subtitle, description, tags_text]))),
                "work_model": work_model or "remoto",
                "experience_years": self._extract_experience_years(description),
            },
            "location": {"raw": location_hint} if location_hint else None,
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _build_description(self, job_data: dict) -> Optional[str]:
        main_description = self._html_to_text(job_data.get("description"))
        more_infos = self._html_to_text(job_data.get("moreInfos"))

        parts: list[str] = []
        if main_description:
            parts.append(main_description)
        if more_infos:
            parts.append(f"Outras Informações\n{more_infos}")

        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _extract_job_data(raw_html: str) -> Optional[dict]:
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            raw_html,
            re.S,
        )
        if not match:
            return None
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        page_props = payload.get("props", {}).get("pageProps", {})
        job_data = page_props.get("jobData")
        return job_data if isinstance(job_data, dict) else None

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

    @classmethod
    def _is_tech_job(cls, text: str) -> bool:
        normalized = (text or "").lower()
        return any(keyword in normalized for keyword in cls.TECH_KEYWORDS)

    @staticmethod
    def _extract_company(job_data: dict) -> Optional[str]:
        company = job_data.get("company")
        if isinstance(company, dict):
            name = company.get("name")
            if name:
                return str(name).strip()
        for key in ("companyDisplayName", "companyDisplayLink"):
            value = job_data.get(key)
            if value:
                return str(value).strip()
        return None

    @classmethod
    def _extract_job_tags_text(cls, job_data: dict) -> Optional[str]:
        tags = job_data.get("jobTags")
        if not isinstance(tags, list):
            return None

        names: list[str] = []
        for item in tags:
            tag = item.get("tag") if isinstance(item, dict) else None
            name = tag.get("name") if isinstance(tag, dict) else None
            normalized_name = cls._normalize_text(name)
            if normalized_name:
                names.append(normalized_name)

        return " ".join(names) if names else None

    @staticmethod
    def _extract_salary_text(job_salary) -> Optional[str]:
        if not isinstance(job_salary, dict):
            return None
        salary_type = str(job_salary.get("type") or "").strip()
        value = job_salary.get("value")
        min_value = None
        max_value = None
        if isinstance(value, dict):
            min_value = value.get("minimum")
            max_value = value.get("maximum")
        if min_value or max_value:
            if min_value and max_value:
                return f"{salary_type} {min_value} - {max_value}".strip()
            return f"{salary_type} {min_value or max_value}".strip()
        return None

    def _extract_salary_value(self, job_salary) -> Optional[float]:
        if not isinstance(job_salary, dict):
            return None
        value = job_salary.get("value")
        if isinstance(value, dict):
            minimum = value.get("minimum")
            maximum = value.get("maximum")
            if isinstance(minimum, (int, float)):
                return float(minimum)
            if isinstance(maximum, (int, float)):
                return float(maximum)
        return None

    @staticmethod
    def _extract_city_state(job_data: dict) -> tuple[Optional[str], Optional[str]]:
        city = RemotarScraper._normalize_text(job_data.get("city"))
        state = RemotarScraper._normalize_text(job_data.get("state"))
        return city, state

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|sênior|sr|staff|principal|lead)\b", normalized):
            return "senior"
        if re.search(r"\b(pleno|mid)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|júnior|jr|new grad|est[aá]gio)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\bpj\b|contractor|contract\b|freelance", normalized):
            return "pj"
        if re.search(r"full[- ]time|efetivo|clt", normalized):
            return "clt"
        if re.search(r"temporary|tempor[aá]rio", normalized):
            return "temporario"
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s+(?:years|anos)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

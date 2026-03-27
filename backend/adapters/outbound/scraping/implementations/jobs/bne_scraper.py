"""
BNE Scraper
Scrapes filtered programming job listings from BNE using the embedded JSON payload.
"""
import html
import json
import re
from typing import Optional

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class BNEScraper(HTTPScraper):
    """Scraper for BNE job listings."""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="bne",
                display_name="BNE",
                description="Scraper de vagas de programador remoto do BNE",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.bne.com.br",
            endpoint="/vagas-de-emprego-para-programador/?Page=1&Function=programador&HomeOffice=True&LinkType=Aut%C3%B4nomo&LinkType=Freelancer&LinkType=Tempor%C3%A1rio",
            enabled=True,
            rate_limit_delay=2.5,
            max_items_per_run=50,
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        response = self.fetch_page(url)
        if not response:
            return None
        return self._parse_detail_page(url, self.parse_html(response.text))

    def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        try:
            url = self.config.get_full_url()
            self.logger.info("Scraping BNE from: %s", url)

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            payload = self._extract_jobs_payload(soup)
            for job in payload[: self.config.max_items_per_run]:
                item = self._parse_job(job)
                if item:
                    items.append(item)

            self.logger.info("Scraped %s items from BNE", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping BNE: %s", exc)
            return items

    def _extract_jobs_payload(self, soup) -> list[dict]:
        hidden_input = soup.select_one("#jobInfoLocal")
        if not hidden_input:
            return []

        raw_value = hidden_input.get("value", "").strip()
        if not raw_value:
            return []

        try:
            return json.loads(html.unescape(raw_value))
        except json.JSONDecodeError as exc:
            self.logger.error("Invalid BNE embedded payload: %s", exc)
            return []

    def _parse_job(self, job: dict) -> Optional[ScrapedItem]:
        url = (job.get("Url") or "").strip()
        if not url:
            return None

        detail_item = self.scrape_url(url)
        detail_data = detail_item.scraped_data if detail_item else None

        description = (detail_data.description if detail_data else None) or self._join_description_parts(
            job.get("Attributions"),
            job.get("GeneralDescription"),
        )
        title = (detail_data.title if detail_data else None) or (
            job.get("Titulo")
            or job.get("Function", {}).get("Name")
            or "Programador"
        )
        city = (detail_data.city if detail_data else None) or job.get("City", {}).get("Name")
        state = (detail_data.state if detail_data else None) or job.get("StateAbbreviation")
        salary_text = self._normalize_text(job.get("AverageWage"))
        salary = self.parse_price(salary_text)
        company = self._normalize_text(job.get("CompanyName")) or (
            detail_data.attributes.get("company") if detail_data else None
        )
        link_type_text = self._normalize_link_type(job.get("LinkType"))
        combined_text = " ".join(filter(None, [title, description, link_type_text]))

        scraped_data = {
            "title": self._normalize_text(title),
            "description": description,
            "price": salary,
            "currency": "BRL",
            "city": city,
            "state": state,
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(combined_text),
                "contract_type": self._infer_contract_type(combined_text),
                "work_model": "remoto" if job.get("Home_Office") else None,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = re.sub(r"\s+", " ", html.unescape(str(value))).strip(" -")
        return normalized or None

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|sênior|sr|lead|principal|staff)\b", normalized):
            return "senior"
        if re.search(r"\b(pleno|mid)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|júnior|jr)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(text: str) -> Optional[str]:
        normalized = text.lower()
        if "pj" in normalized:
            return "pj"
        if "autonomo" in normalized or "autônomo" in normalized:
            return "pj"
        if "freelancer" in normalized or "freela" in normalized:
            return "freelancer"
        if "tempor" in normalized:
            return "temporario"
        if "clt" in normalized:
            return "clt"
        return None

    @classmethod
    def _normalize_link_type(cls, value) -> Optional[str]:
        if isinstance(value, list):
            normalized_items = [cls._normalize_text(item) for item in value]
            return " ".join(item for item in normalized_items if item) or None
        return cls._normalize_text(value)

    def _extract_detail_description(self, url: str) -> Optional[str]:
        response = self.fetch_page(url)
        if not response:
            return None

        soup = self.parse_html(response.text)
        return self._extract_detail_description_from_soup(soup)

    def _parse_detail_page(self, url: str, soup) -> Optional[ScrapedItem]:
        job_posting = self._extract_job_posting_payload(soup)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        title = (
            self.extract_text(soup, "h1, .job__title, .job__name")
            or self._normalize_text(job_posting.get("title") if isinstance(job_posting, dict) else None)
            or "Programador"
        )
        description = self._extract_detail_description_from_soup(soup) or self._normalize_text(
            self._extract_job_posting_description(job_posting)
        )
        city, state = self._extract_city_state_from_job_posting(job_posting)
        if not city or not state:
            city, state = self._extract_city_state_from_text(page_text)
        salary_text = self._extract_salary_text_from_job_posting(job_posting) or self._normalize_text(
            self.extract_text(soup, ".job__salary, .salary, [class*='salary']")
        )
        combined_text = " ".join(filter(None, [title, description, page_text]))

        scraped_data = {
            "title": title,
            "description": description,
            "price": self.parse_price(salary_text),
            "currency": "BRL",
            "city": city,
            "state": state,
            "attributes": {
                "company": self._extract_company_from_job_posting(job_posting),
                "salary_text": salary_text,
                "seniority": self._infer_seniority(combined_text),
                "contract_type": self._infer_contract_type(combined_text),
                "work_model": "remoto" if re.search(r"\b(home office|remot[oa])\b", combined_text, re.IGNORECASE) else None,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_detail_description_from_soup(self, soup) -> Optional[str]:
        attributions = self._extract_section_text(soup, ".job__info.atribuicoes__vaga")
        general_description = self._extract_section_text(soup, ".job__info.descricao__vaga")
        combined = self._join_description_parts(attributions, general_description)
        return combined

    @classmethod
    def _extract_section_text(cls, soup, selector: str) -> Optional[str]:
        section = soup.select_one(selector)
        if not section:
            return None

        text = html.unescape(section.get_text("\n", strip=True))
        lines: list[str] = []

        for raw_line in text.splitlines():
            normalized_line = cls._normalize_text(raw_line)
            if not normalized_line:
                continue
            if normalized_line.lower() in {"atribuições", "descricao geral", "descrição geral"}:
                continue
            lines.append(normalized_line)

        if not lines:
            return None

        return " ".join(lines)

    def _extract_job_posting_payload(self, soup) -> dict:
        for script in soup.select('script[type="application/ld+json"]'):
            raw_payload = script.string or script.get_text() or ""
            if "JobPosting" not in raw_payload:
                continue
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
                return payload
        return {}

    @staticmethod
    def _extract_job_posting_description(payload: dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        description = payload.get("description")
        if not description:
            return None
        description = html.unescape(str(description))
        description = re.sub(r"<br\\s*/?>", "\n", description, flags=re.IGNORECASE)
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"[ \t]+", " ", description)
        description = re.sub(r"\n\s*\n+", "\n\n", description)
        return description.strip() or None

    @staticmethod
    def _extract_company_from_job_posting(payload: dict) -> Optional[str]:
        hiring = payload.get("hiringOrganization") if isinstance(payload, dict) else None
        if isinstance(hiring, dict):
            return BNEScraper._normalize_text(hiring.get("name"))
        return None

    @staticmethod
    def _extract_city_state_from_job_posting(payload: dict) -> tuple[Optional[str], Optional[str]]:
        locations = payload.get("jobLocation") if isinstance(payload, dict) else None
        if isinstance(locations, dict):
            locations = [locations]
        if not isinstance(locations, list):
            return None, None
        for location in locations:
            address = location.get("address") if isinstance(location, dict) else None
            if not isinstance(address, dict):
                continue
            city = BNEScraper._normalize_text(address.get("addressLocality"))
            state = BNEScraper._normalize_text(address.get("addressRegion"))
            if city or state:
                return city, state
        return None, None

    @staticmethod
    def _extract_city_state_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
        match = re.search(r"([A-Za-zÀ-ÿ\s]+?)[/-]\s*([A-Z]{2})\b", text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None

    @staticmethod
    def _extract_salary_text_from_job_posting(payload: dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        salary = payload.get("baseSalary")
        if not isinstance(salary, dict):
            return None
        value = salary.get("value")
        if isinstance(value, dict):
            minimum = value.get("minValue") or value.get("value")
            maximum = value.get("maxValue")
            currency = salary.get("currency") or "BRL"
            if minimum is not None and maximum is not None:
                return f"{currency} {minimum} - {currency} {maximum}"
            if minimum is not None:
                return f"{currency} {minimum}"
        return None

    @classmethod
    def _join_description_parts(cls, attributions: Optional[str], general_description: Optional[str]) -> Optional[str]:
        pieces = [cls._normalize_text(attributions), cls._normalize_text(general_description)]
        joined = "\n\n".join(piece for piece in pieces if piece)
        return joined or None

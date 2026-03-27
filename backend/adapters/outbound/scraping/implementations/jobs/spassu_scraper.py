"""
Spassu Scraper
Scrapes software and IT job openings from Spassu careers.
"""
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class SpassuScraper(HTTPScraper):
    """Scraper for Spassu Zoho Recruit careers."""

    TECH_KEYWORDS = (
        "desenvolvedor",
        "developer",
        "fullstack",
        "full stack",
        "python",
        "react",
        "java",
        "angular",
        "software",
        "arquiteto",
        "engineer",
        "engenheiro",
        "dados",
        "data",
        "devops",
        "cloud",
        "scrum",
        "qa",
        "frontend",
        "backend",
        "back-end",
        "front-end",
        "ti",
        "tech",
        "api",
        "fastapi",
    )

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="spassu",
                display_name="Spassu Careers",
                description="Scraper de vagas de TI e desenvolvimento da Spassu",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://spassu.zohorecruit.com",
            endpoint="/jobs/Careers",
            enabled=True,
            timeout=45,
            rate_limit_delay=2.0,
            max_items_per_run=25,
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
        for anchor in soup.select("a[href*='/jobs/Careers/']"):
            href = (anchor.get("href") or "").strip()
            if "?source=CareerSite" not in href:
                continue
            url = urljoin(self.config.base_url, href).split("&", 1)[0]
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

        title = self.extract_text(soup, "h1")
        if not title:
            return None
        description = self._extract_description(soup)
        if not self._is_tech_job(" ".join(filter(None, [title, description]))):
            return None

        company = "Spassu"
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        info_map = self._extract_job_info_map(soup)
        work_model_value = info_map.get("Trabalho remoto")
        work_model = "remoto" if self._is_remote_job(work_model_value, page_text) else None
        contract_type = info_map.get("Tipo de emprego")
        posted_at = info_map.get("Data da abertura")
        city = info_map.get("Cidade")
        state = info_map.get("Estado/Província") or info_map.get("Estado")
        zip_code = self._normalize_zip_code(info_map.get("CEP/Código postal") or info_map.get("CEP"))
        country = info_map.get("País") or info_map.get("Pais")

        scraped_data = {
            "title": title,
            "description": description,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "attributes": {
                "company": company,
                "country": country,
                "salary_text": None,
                "seniority": self._infer_seniority(" ".join(filter(None, [title, description]))),
                "contract_type": self._infer_contract_type(contract_type),
                "work_model": work_model,
                "experience_years": self._extract_experience_years(description),
            },
        }

        if posted_at:
            scraped_data["description"] = f"Publicado em {posted_at}.\n\n{description}" if description else f"Publicado em {posted_at}."

        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @classmethod
    def _is_tech_job(cls, text: str) -> bool:
        normalized = (text or "").lower()
        return any(keyword in normalized for keyword in cls.TECH_KEYWORDS)

    @staticmethod
    def _extract_description(soup) -> Optional[str]:
        heading = soup.find(re.compile(r"^h[23]$"), string=re.compile(r"Descrição da vaga", re.I))
        if not heading:
            meta_description = soup.select_one('meta[name="description"]')
            return meta_description.get("content", "").strip() if meta_description else None

        container = heading.find_parent()
        if not container:
            return None

        blocks: list[str] = []
        for node in container.find_all(["p", "div", "li", "h3"], recursive=True):
            text = " ".join(node.get_text(" ", strip=True).split())
            if not text or text == "Descrição da vaga":
                continue
            if text == "Estou interessado":
                continue
            blocks.append(text)
        deduped: list[str] = []
        seen: set[str] = set()
        for block in blocks:
            if block in seen:
                continue
            seen.add(block)
            deduped.append(block)
        return "\n\n".join(deduped) or None

    @staticmethod
    def _extract_job_info_value(soup, label: str) -> Optional[str]:
        return SpassuScraper._extract_job_info_map(soup).get(label)

    @staticmethod
    def _extract_job_info_map(soup) -> dict[str, str]:
        heading = soup.find(re.compile(r"^h[23]$"), string=re.compile(r"Informações da vaga", re.I))
        if not heading:
            return {}
        section = heading.find_parent()
        if not section:
            return {}

        label_variants = [
            "Data da abertura",
            "Tipo de emprego",
            "Indústria",
            "Cidade",
            "Estado/Província",
            "Estado",
            "País",
            "Pais",
            "CEP/Código postal",
            "CEP",
            "Trabalho remoto",
        ]
        extracted: dict[str, str] = {}
        seen_lines: set[str] = set()

        for node in section.find_all(["li", "p", "div"], recursive=True):
            text = " ".join(node.get_text(" ", strip=True).split())
            if not text or text == "Informações da vaga" or text in seen_lines:
                continue
            seen_lines.add(text)

            for label in label_variants:
                match = re.match(rf"^{re.escape(label)}\s*[:\-]?\s*(.+)$", text, flags=re.I)
                if match:
                    extracted[label] = match.group(1).strip()
                    break

        return extracted

    @staticmethod
    def _is_remote_job(work_model_value: Optional[str], page_text: str) -> bool:
        normalized_info = (work_model_value or "").strip().lower()
        if normalized_info in {"sim", "yes", "true"}:
            return True
        return "trabalho remoto" in page_text.lower()

    @staticmethod
    def _normalize_zip_code(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) == 8:
            return digits
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _infer_seniority(text: str) -> Optional[str]:
        normalized = text.lower()
        if re.search(r"\b(senior|sênior|sr)\b", normalized):
            return "senior"
        if re.search(r"\b(pleno|pl)\b", normalized):
            return "pleno"
        if re.search(r"\b(junior|júnior|jr)\b", normalized):
            return "junior"
        return None

    @staticmethod
    def _infer_contract_type(value: Optional[str]) -> Optional[str]:
        normalized = (value or "").lower()
        if "efetivo" in normalized or "full time" in normalized:
            return "clt"
        if "tempor" in normalized:
            return "temporario"
        return None

    @staticmethod
    def _extract_experience_years(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d+)\+?\s+(?:anos|years)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

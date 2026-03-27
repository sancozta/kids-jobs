"""
Catho Scraper
Scrapes senior remote contractor-oriented programming jobs from Catho.
"""
import html
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedData, ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, ScrapingStrategy, SourceType


class CathoScraper(HTTPScraper):
    """Scraper for Catho job listings"""

    TITLE_KEYWORDS = (
        "programador",
        "desenvolvedor",
        "developer",
        "software",
        "backend",
        "back-end",
        "frontend",
        "front-end",
        "full stack",
        ".net",
        "java",
        "php",
        "python",
    )

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="catho",
                display_name="Catho",
                description="Scraper de vagas de emprego da Catho",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.catho.com.br",
            endpoint="/vagas/programador-senior/?order=dataAtualizacao&contract_type_id%5B0%5D=6&work_model%5B0%5D=remote",
            enabled=True,
            timeout=45,
            max_retries=2,
            rate_limit_delay=2.5,
            max_items_per_run=50,
            strategy=ScrapingStrategy.BROWSER_PLAYWRIGHT,
            extra_config={
                # Warm-up na home melhora chance de receber cookies/sessão antes da URL alvo.
                "playwright_warmup_url": "https://www.catho.com.br/",
                "playwright_wait_until": "domcontentloaded",
                "playwright_wait_after_load_ms": 4200,
                "playwright_persistent_session": True,
                "playwright_headful_fallback": True,
                "playwright_virtual_display_size": "1440x960",
                "playwright_blocked_title_keywords": [
                    "operação inválida",
                    "operacao invalida",
                ],
            },
        )

    def __init__(self, config: Optional[ScraperConfig] = None):
        super().__init__(config)

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        response = self.fetch_page(url)
        if not response:
            return None
        return self._parse_detail_page(url, response.text)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping Catho from: {url}")
            response = self.fetch_page(url)
            if not response:
                return items
            soup = self.parse_html(response.text)
            listings = soup.select(
                "article, "
                "article.job-card, "
                "li.job_list_item, "
                "div[class*='JobCard'], "
                "div[class*='vaga']"
            )
            seen_urls: set[str] = set()
            for idx, listing in enumerate(listings):
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self._parse_listing(listing)
                    if item and item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
            self.logger.info(f"Scraped {len(items)} items from Catho")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping Catho: {e}")
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        try:
            title = self.extract_text(
                listing,
                "h1 a, h2 a, h3 a, .titulo-vaga, .job-title, [class*='JobTitle'], [class*='SearchResultCardTitle'] a, [class*='SearchResultCardTitle']",
            )
            company = self.extract_text(
                listing,
                ".company-name, .empresa, [class*='Company'], [class*='SearchResultCardCompany'], p",
            )
            salary_text = self.extract_text(
                listing,
                ".salary, .salario, [class*='Salary'], [class*='SearchResultCardSalary']",
            )
            salary = self.parse_price(salary_text)
            link_elem = listing.select_one("h1 a[href*='/vagas/'], h2 a[href*='/vagas/'], h3 a[href*='/vagas/'], a[href*='/vagas/']")
            url = urljoin(self.config.base_url, link_elem.get("href", "")) if link_elem else None
            if not url or "/vagas/" not in url:
                return None

            location_raw = self.extract_text(
                listing,
                ".location, .local, [class*='Location'], [class*='SearchResultCardLocation'], a[href*='/vagas/programador-senior/']",
            )
            description = self._extract_detail_description(url) or self.extract_text(
                listing,
                ".description, [class*='SearchResultCardDescription'], [class*='description'], div",
            )

            combined_text = " ".join(listing.get_text(" ", strip=True).split())
            title = title or self.extract_text(link_elem, "span, strong, div") if link_elem else title
            title = title or combined_text[:180]
            if not self._looks_like_target_job(title, description or combined_text):
                return None

            company = self._sanitize_company(company, title)
            experience_years = self._extract_experience_years(combined_text)

            scraped_data = ScrapedData(
                title=title,
                description=description,
                price=salary,
                currency="BRL",
                city=None,
                state=None,
                attributes={
                    "company": company,
                    "salary_text": salary_text,
                    "location_raw": location_raw,
                    "seniority": "senior",
                    "contract_type": "pj",
                    "work_model": "remoto",
                    "experience_years": experience_years,
                },
            )

            return self.build_scraped_item(
                url=url,
                scraped_data=scraped_data,
            )
        except Exception as e:
            self.logger.error(f"Error parsing listing: {e}")
            return None

    def _looks_like_target_job(self, title: Optional[str], context_text: Optional[str]) -> bool:
        normalized = self._normalize_text(" ".join(filter(None, [title, context_text])))
        if not normalized:
            return False
        return any(keyword in normalized for keyword in self.TITLE_KEYWORDS)

    @staticmethod
    def _normalize_text(value: Optional[str]) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip().lower()

    @staticmethod
    def _sanitize_company(company: Optional[str], title: Optional[str]) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", (company or "")).strip(" -")
        if not cleaned:
            return None
        if title and cleaned.lower() == title.lower():
            return None
        return cleaned

    @staticmethod
    def _extract_experience_years(text: str) -> Optional[int]:
        range_match = re.search(r"entre\s+(\d+)\s+e\s+\d+\s+anos", text, re.IGNORECASE)
        if range_match:
            return int(range_match.group(1))

        single_match = re.search(r"(\d+)\s*\+?\s*anos", text, re.IGNORECASE)
        if single_match:
            return int(single_match.group(1))
        return None

    def _extract_detail_description(self, url: str) -> Optional[str]:
        response = self.fetch_page(url)
        if not response:
            return None

        return self._extract_detail_description_from_soup(self.parse_html(response.text))

    def _parse_detail_page(self, url: str, raw_html: str) -> Optional[ScrapedItem]:
        soup = self.parse_html(raw_html)
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        title = self._extract_detail_title(soup, raw_html, url)
        description = self._extract_detail_description_from_soup(soup)
        salary_text = self._extract_detail_salary_text(raw_html, page_text)
        location_raw = self._extract_detail_location(soup, raw_html)
        company = self._sanitize_company(self._extract_detail_company(soup), title)
        experience_years = self._extract_experience_years(page_text)

        scraped_data = ScrapedData(
            title=title,
            description=description,
            price=self.parse_price(salary_text),
            currency="BRL",
            attributes={
                "company": company,
                "salary_text": salary_text,
                "location_raw": location_raw,
                "seniority": "senior" if re.search(r"\b(senior|sênior|sr)\b", page_text, re.IGNORECASE) else None,
                "contract_type": "pj" if re.search(r"\bpj\b", page_text, re.IGNORECASE) else "pj",
                "work_model": "remoto" if re.search(r"\b(remoto|home office)\b", page_text, re.IGNORECASE) else "remoto",
                "experience_years": experience_years,
            },
        )
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_detail_description_from_soup(self, soup) -> Optional[str]:
        section = soup.select_one("#job-description .job-description")
        if not section:
            for heading in soup.find_all(["h2", "h3"]):
                heading_text = self._normalize_text(heading.get_text(" ", strip=True))
                if heading_text == "sobre a vaga":
                    sibling = heading.find_next(["div", "section", "p"])
                    if sibling:
                        section = sibling
                        break

        if not section:
            return None

        description = html.unescape(" ".join(section.get_text("\n", strip=True).split()))
        return description or None

    def _extract_detail_title(self, soup, raw_html: str, url: str) -> str:
        meta_title = soup.select_one('meta[property="og:title"], meta[name="og:title"]')
        if meta_title and meta_title.get("content"):
            content = meta_title["content"].strip()
            match = re.search(r"Vaga de Emprego de\s+(.+?)(?:,\s*[^,]+?\s*/\s*[A-Z]{2})?$", content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            if content:
                return re.sub(r"\s+\|\s+Catho.*$", "", content).strip()

        title_tag = soup.title.get_text(" ", strip=True) if soup.title else ""
        if title_tag:
            match = re.search(r"Vaga de Emprego de\s+(.+?)(?:,\s*[^,]+?\s*/\s*[A-Z]{2})?$", title_tag, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        heading = soup.select_one("main h1, header h1, h1")
        if heading:
            text = " ".join(heading.get_text(" ", strip=True).split())
            if text:
                return text

        slug = url.rstrip("/").split("/")[-2] if url.rstrip("/").count("/") >= 4 else url.rstrip("/").split("/")[-1]
        return slug.replace("-", " ").strip().title()

    @staticmethod
    def _extract_detail_salary_text(raw_html: str, page_text: str) -> Optional[str]:
        meta_match = re.search(r"faixa salarial:\s*(.+?)\.\s*(?:Vaga Incluída|</|\"|\')", raw_html, re.IGNORECASE)
        if meta_match:
            return re.sub(r"\s+", " ", html.unescape(meta_match.group(1))).strip(" -")

        text_match = re.search(r"(De\s+R\$\s?[\d\.\,]+\s+a\s+R\$\s?[\d\.\,]+|R\$\s?[\d\.\,]+(?:\s*-\s*R\$\s?[\d\.\,]+)?)", page_text, re.IGNORECASE)
        return text_match.group(1).strip() if text_match else None

    @staticmethod
    def _extract_detail_location(soup, raw_html: str) -> Optional[str]:
        for anchor in soup.select("a[title]"):
            title = " ".join(anchor.get("title", "").split())
            if re.search(r"[A-Za-zÀ-ÿ\s]+ - [A-Z]{2}", title):
                return title.split("(", 1)[0].strip()

        meta_match = re.search(r"Vaga de Emprego de\s+.+?,\s*([^,]+?\s*/\s*[A-Z]{2})", raw_html, re.IGNORECASE)
        if meta_match:
            return meta_match.group(1).strip().replace("/", "-")
        return None

    @staticmethod
    def _extract_detail_company(soup) -> Optional[str]:
        for selector in (
            "[data-testid='company-name']",
            "[class*='CompanyInfo']",
            "[class*='companyName']",
            "[class*='company-name']",
        ):
            element = soup.select_one(selector)
            if element:
                text = " ".join(element.get_text(" ", strip=True).split())
                if text:
                    return text
        return None

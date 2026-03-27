"""
InfoJobs Scraper
Scrapes job listings from InfoJobs Brasil
"""
import html
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import SourceType, ScrapingCategory


class InfoJobsScraper(HTTPScraper):
    """Scraper for InfoJobs job listings"""

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="infojobs",
                display_name="InfoJobs",
                description="Scraper de vagas de emprego do InfoJobs",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.infojobs.com.br",
            endpoint="/vagas-de-emprego-programador+s%c3%aanior-trabalho-home-office.aspx?tipocontrato=17",
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
        soup = self.parse_html(response.text)
        return self._parse_detail_page(url, soup)

    def scrape(self) -> list[ScrapedItem]:
        items = []
        try:
            url = self.config.get_full_url()
            self.logger.info(f"Scraping InfoJobs from: {url}")

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select(".js_vacancyLoad.js_cardLink[data-href], .js_rowCard .js_vacancyLoad[data-href]")
            seen_urls: set[str] = set()

            for listing in listings:
                href = listing.get("data-href", "").strip() or listing.get("href", "").strip()
                listing_url = urljoin(self.config.base_url, href).split("?")[0]
                if not listing_url or listing_url in seen_urls:
                    continue
                seen_urls.add(listing_url)

                idx = len(items)
                if self.config.max_items_per_run and idx >= self.config.max_items_per_run:
                    break
                try:
                    item = self._parse_listing(listing, listing_url)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.error(f"Error parsing listing: {e}")
                    continue

            self.logger.info(f"Scraped {len(items)} items from InfoJobs")
            return items
        except Exception as e:
            self.logger.error(f"Error scraping InfoJobs: {e}")
            return items

    def _parse_listing(self, listing, listing_url: str) -> Optional[ScrapedItem]:
        try:
            url = listing_url
            if not url:
                return None

            context_text = " ".join(listing.get_text(" ", strip=True).split())
            detail_item = self.scrape_url(url)
            detail_data = detail_item.scraped_data if detail_item else None

            title = self.extract_text(listing, "h1, h2, h3") or None
            if not title:
                slug = url.split("/vaga-de-", 1)[-1].split("__", 1)[0]
                title = slug.replace("-", " ").strip().title()
            if not title and detail_data:
                title = detail_data.title

            salary_text = self._extract_salary_text(listing, context_text)
            salary = self.parse_price(salary_text)
            location = self._extract_location(listing, context_text)
            detail_location = None
            if detail_data and detail_data.city and detail_data.state:
                detail_location = f"{detail_data.city} - {detail_data.state}"
            company = self._extract_company(listing) or (
                detail_data.attributes.get("company") if detail_data and detail_data.attributes else None
            )
            experience_years = self._extract_experience_years(context_text)
            work_model = "remoto" if "home office" in context_text.lower() else None
            seniority = "senior" if re.search(r"\b(senior|sênior|sr)\b", context_text, re.IGNORECASE) else None

            scraped_data = {
                "title": title,
                "description": (detail_data.description if detail_data else None) or self._extract_description(listing, context_text),
                "price": salary,
                "currency": "BRL",
                "city": detail_data.city if detail_data else None,
                "state": detail_data.state if detail_data else None,
                "location": {"raw": detail_location or location},
                "attributes": {
                    "company": company,
                    "salary_text": salary_text,
                    "seniority": seniority or "senior",
                    "contract_type": "pj",
                    "work_model": work_model or "remoto",
                    "experience_years": experience_years,
                },
            }

            return self.build_scraped_item(
                url=url,
                scraped_data=scraped_data,
            )
        except Exception as e:
            self.logger.error(f"Error parsing listing: {e}")
            return None

    @staticmethod
    def _extract_salary_text(listing, context_text: str) -> Optional[str]:
        salary_block = listing.select_one(".icon-money, svg.icon-money")
        if salary_block and salary_block.parent:
            candidate = " ".join(salary_block.parent.get_text(" ", strip=True).split())
            if candidate:
                return candidate

        match = re.search(r"(R\$\s?[\d\.\,]+(?:\s*-\s*R\$\s?[\d\.\,]+)?|A combinar)", context_text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_location(listing, context_text: str) -> Optional[str]:
        for candidate in listing.select(".mb-8"):
            text = " ".join(candidate.get_text(" ", strip=True).split())
            matches = re.findall(r"([A-Za-zÀ-ÿ\s]+?)\s*-\s*([A-Z]{2})", text)
            if matches:
                city, state = matches[-1]
                return f"{city.strip()} - {state.strip()}"

        matches = re.findall(r"([A-Za-zÀ-ÿ\s]+?)\s*-\s*([A-Z]{2})", context_text)
        if matches:
            city, state = matches[-1]
            return f"{city.strip()} - {state.strip()}"
        return None

    @staticmethod
    def _extract_company(listing) -> Optional[str]:
        for anchor in listing.select("a[href*='/empresa-']"):
            company = " ".join(anchor.get_text(" ", strip=True).split())
            if company:
                return company
        text_body = listing.select_one(".text-body")
        if text_body:
            company = " ".join(text_body.get_text(" ", strip=True).split())
            if company:
                return company
        return None

    @staticmethod
    def _extract_description(listing, fallback: str) -> Optional[str]:
        candidates = listing.select("div.text-medium")
        if candidates:
            return " ".join(candidates[-1].get_text(" ", strip=True).split())
        return fallback[:500] if fallback else None

    @staticmethod
    def _extract_experience_years(context_text: str) -> Optional[int]:
        range_match = re.search(r"Entre\s+(\d+)\s+e\s+\d+\s+anos", context_text, re.IGNORECASE)
        if range_match:
            return int(range_match.group(1))

        single_match = re.search(r"(\d+)\s*\+?\s*anos", context_text, re.IGNORECASE)
        if single_match:
            return int(single_match.group(1))
        return None

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
            self.extract_text(soup, "h1, h2")
            or self._normalize_text_block(job_posting.get("title") if isinstance(job_posting, dict) else None)
            or self._title_from_url(url)
        )
        description = self._extract_detail_description_from_soup(soup) or self._normalize_text_block(
            self._extract_job_posting_description(job_posting)
        )
        location_text = self._extract_job_posting_location(job_posting) or self._extract_location(soup, page_text)
        city, state = self._parse_city_state(location_text)
        salary_text = self._extract_job_posting_salary(job_posting) or self._extract_salary_text(soup, page_text)
        experience_years = self._extract_experience_years(" ".join(filter(None, [page_text, description])))
        company = self._extract_job_posting_company(job_posting) or self._extract_company(soup)
        combined_text = " ".join(filter(None, [title, description, page_text, location_text]))

        scraped_data = {
            "title": title,
            "description": description,
            "price": self.parse_price(salary_text),
            "currency": "BRL",
            "city": city,
            "state": state,
            "location": {"raw": location_text} if location_text else None,
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": "senior" if re.search(r"\b(senior|sênior|sr)\b", combined_text, re.IGNORECASE) else None,
                "contract_type": "pj",
                "work_model": "remoto" if re.search(r"\b(remoto|home office)\b", combined_text, re.IGNORECASE) else "remoto",
                "experience_years": experience_years,
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_detail_description_from_soup(self, soup) -> Optional[str]:
        panel = soup.select_one(".js_vacancyDataPanels")
        if panel:
            text = self._normalize_text_block(panel.get_text("\n", strip=True))
            if text:
                return text

        for script in soup.select('script[type="application/ld+json"]'):
            raw_json = (script.string or script.get_text() or "").strip()
            if "JobPosting" not in raw_json:
                continue
            try:
                payload = json.loads(raw_json, strict=False)
            except json.JSONDecodeError:
                continue
            description = payload.get("description") if isinstance(payload, dict) else None
            if description:
                return self._normalize_text_block(html.unescape(description))

        return None

    @staticmethod
    def _extract_job_posting_payload(soup) -> dict:
        for script in soup.select('script[type="application/ld+json"]'):
            raw_json = (script.string or script.get_text() or "").strip()
            if "JobPosting" not in raw_json:
                continue
            try:
                payload = json.loads(raw_json, strict=False)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
                return payload
        return {}

    @staticmethod
    def _extract_job_posting_description(payload: dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        return payload.get("description")

    @staticmethod
    def _extract_job_posting_company(payload: dict) -> Optional[str]:
        hiring = payload.get("hiringOrganization") if isinstance(payload, dict) else None
        if isinstance(hiring, dict):
            name = hiring.get("name")
            return " ".join(str(name).split()) if name else None
        return None

    @staticmethod
    def _extract_job_posting_location(payload: dict) -> Optional[str]:
        job_location = payload.get("jobLocation") if isinstance(payload, dict) else None
        if isinstance(job_location, dict):
            job_location = [job_location]
        if not isinstance(job_location, list):
            return None
        for location in job_location:
            address = location.get("address") if isinstance(location, dict) else None
            if not isinstance(address, dict):
                continue
            city = address.get("addressLocality")
            state = address.get("addressRegion")
            if city and state:
                return f"{city} - {state}"
        return None

    @staticmethod
    def _extract_job_posting_salary(payload: dict) -> Optional[str]:
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

    @staticmethod
    def _parse_city_state(location_text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not location_text:
            return None, None
        match = re.search(r"([A-Za-zÀ-ÿ\s]+?)\s*-\s*([A-Z]{2})", location_text)
        if not match:
            return None, None
        return match.group(1).strip(), match.group(2).strip()

    @staticmethod
    def _title_from_url(url: str) -> str:
        slug = url.split("/vaga-de-", 1)[-1].split("__", 1)[0]
        return slug.replace("-", " ").strip().title()

    @staticmethod
    def _normalize_text_block(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        value = html.unescape(value)
        value = re.sub(r"<br\\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n\s*\n+", "\n\n", value)
        value = re.sub(r"\s+\n", "\n", value)
        value = re.sub(r"\n\s+", "\n", value)
        normalized = value.strip()
        return normalized or None

"""
Nerdin Scraper
Scrapes filtered remote PJ tech jobs from Nerdin.
"""
import html
import json
import re
from typing import Optional
from urllib.parse import urljoin

from adapters.outbound.scraping.http_scraper import HTTPScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class NerdinScraper(HTTPScraper):
    """Scraper for Nerdin job listings."""

    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U0001F1E6-\U0001F1FF"
        "\u200d"
        "\ufe0f"
        "]+",
        flags=re.UNICODE,
    )
    TITLE_BADGE_PATTERN = re.compile(r"(?:\s|[-|])*(?:NOVA|NOVO)\s*$", flags=re.IGNORECASE)
    DESCRIPTION_NOISE_PATTERNS = (
        r"^Quero me Candidatar$",
        r"^Desbloqueie o Contato Direto da Empresa\.?$",
        r"^Não fique invisível no processo seletivo\.?$",
        r"^Desbloquear contato$",
        r"^Contato sem intermediação$",
        r"^Aumente suas chances$",
        r"^Vagas VIP exclusivas$",
        r"^Quero Prioridade$",
        r"^Seja Premium$",
        r"^E-mail:\s*.+$",
        r"^Whats:\s*.+$",
        r"^Publicada .+$",
        r"^\d+\s+Vaga(?:s)?$",
        r"^Nível:\s*.+$",
        r"^Contratação\s+.+$",
        r"^Sal[aá]rio\s+.+$",
        r"^Não informado\.?$",
    )

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="nerdin",
                display_name="Nerdin",
                description="Scraper de vagas PJ e home office do Nerdin",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.HTTP,
                version="1.0.0",
            ),
            base_url="https://www.nerdin.com.br",
            endpoint="/vagas.php?filtro_area%5B%5D=3&filtro_area%5B%5D=5&filtro_area%5B%5D=1&filtro_area%5B%5D=4&filtro_area%5B%5D=2&filtro_home_office=1&filtro_pj=1",
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
            self.logger.info("Scraping Nerdin from: %s", url)

            response = self.fetch_page(url)
            if not response:
                return items

            soup = self.parse_html(response.text)
            listings = soup.select(".vaga-card")
            seen_urls: set[str] = set()

            for listing in listings:
                if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                    break
                item = self._parse_listing(listing)
                if item and item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)

            self.logger.info("Scraped %s items from Nerdin", len(items))
            return items
        except Exception as exc:
            self.logger.error("Error scraping Nerdin: %s", exc)
            return items

    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        link_elem = listing.select_one("a.btn-ver-vaga[href]")
        url = urljoin(self.config.base_url, link_elem.get("href", "")) if link_elem else None
        if not url:
            return None

        title = self._clean_title(self.extract_text(listing, ".vaga-titulo"))
        salary_text = self.extract_text(listing, ".vaga-salario")
        company = self._clean_company(self.extract_text(listing, ".vaga-empresa"))
        location_raw = self.extract_text(listing, ".vaga-local")
        hashtags = [" ".join(tag.get_text(" ", strip=True).split()) for tag in listing.select(".vaga-hashtags .hashtag")]
        detail_description = self._extract_detail_description(url)
        description = detail_description or " ".join(tag for tag in hashtags if tag)
        combined_text = " ".join(filter(None, [title, description, location_raw]))

        scraped_data = {
            "title": title,
            "description": description or None,
            "price": self._extract_price(salary_text),
            "currency": "BRL",
            "location": {"raw": location_raw},
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(combined_text),
                "contract_type": "pj",
                "work_model": "remoto",
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    @staticmethod
    def _clean_company(company: Optional[str]) -> Optional[str]:
        if not company:
            return None
        company = company.replace("Verificado", "").replace("Whatsapp", "")
        company = re.sub(r"\s+", " ", company).strip(" -")
        return company or None

    @classmethod
    def _clean_title(cls, title: Optional[str]) -> Optional[str]:
        text = cls._sanitize_text(title)
        if not text:
            return None
        text = cls.TITLE_BADGE_PATTERN.sub("", text).strip(" -|")
        return text or None

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

    def _extract_price(self, salary_text: Optional[str]) -> Optional[float]:
        if not salary_text:
            return None
        first_value = re.search(r"R\$\s?[\d\.\,]+", salary_text)
        if not first_value:
            return None
        return self.parse_price(first_value.group(0))

    def _extract_detail_description(self, url: str) -> Optional[str]:
        response = self.fetch_page(url)
        if not response:
            return None

        soup = self.parse_html(response.text)
        return self._extract_detail_description_from_soup(soup)

    def _parse_detail_page(self, url: str, soup) -> Optional[ScrapedItem]:
        job_posting = self._extract_job_posting_payload(soup)
        title = self._clean_title(
            self.extract_text(soup, "h1, h2")
            or job_posting.get("title")
            or self._title_from_url(url)
        )
        description = self._extract_detail_description_from_soup(soup)
        if not description:
            description = self._clean_description_text(job_posting.get("description"))

        page_text = " ".join(soup.get_text(" ", strip=True).split())
        salary_text = self._extract_salary_text_from_soup(soup, job_posting)
        company = self._clean_company(
            self.extract_text(soup, ".empresa, .company, .vaga-empresa")
            or self._extract_company_from_job_posting(job_posting)
        )
        combined_text = " ".join(filter(None, [title, description, page_text]))

        scraped_data = {
            "title": title,
            "description": description,
            "price": self._extract_price(salary_text),
            "currency": "BRL",
            "attributes": {
                "company": company,
                "salary_text": salary_text,
                "seniority": self._infer_seniority(combined_text),
                "contract_type": "pj",
                "work_model": "remoto" if re.search(r"\b(home office|remot[oa])\b", combined_text, re.IGNORECASE) else "remoto",
            },
        }
        return self.build_scraped_item(url=url, scraped_data=scraped_data)

    def _extract_detail_description_from_soup(self, soup) -> Optional[str]:
        about_lines = self._extract_about_lines(soup)
        requirements_lines = self._extract_requirements_lines(soup)

        about = self._format_about_section(about_lines)
        requirements = self._format_requirements_section(requirements_lines)

        combined = " ".join(part for part in [about, requirements] if part)
        return combined or None

    @staticmethod
    def _extract_salary_text_from_page(text: str) -> Optional[str]:
        if not text:
            return None
        salary_match = re.search(r"R\$\s?[\d\.\,]+(?:\s*-\s*R\$\s?[\d\.\,]+)?", text)
        if salary_match:
            return salary_match.group(0)
        if re.search(r"sal[aá]rio a combinar", text, re.IGNORECASE):
            return "Salário a combinar"
        return None

    def _extract_salary_text_from_soup(self, soup, job_posting: dict) -> Optional[str]:
        salary_badge = self._sanitize_text(self.extract_text(soup, ".vaga-salario"))
        if salary_badge:
            return salary_badge

        structured_salary = self._extract_salary_text_from_job_posting(job_posting)
        if structured_salary:
            return structured_salary

        return None

    @staticmethod
    def _title_from_url(url: str) -> str:
        slug = url.rstrip("/").rsplit("/", 1)[-1].replace(".php", "")
        slug = slug.split("-", 1)[0] if slug.startswith("vaga_emprego") else slug
        return slug.replace("-", " ").strip().title() or "Vaga Nerdin"

    def _extract_about_lines(self, soup) -> list[str]:
        section = soup.select_one("#sobre-pane")
        if not section:
            return []

        content_blocks = []
        for child in section.find_all("div", recursive=False):
            classes = set(child.get("class") or [])
            if "mb-3" not in classes:
                continue
            if "py-2" in classes or "d-lg-none" in classes:
                continue
            content_blocks.append(child)

        content = content_blocks[0] if content_blocks else section
        return self._extract_clean_lines(
            content,
            title=None,
            remove_direct_divs=False,
        )

    def _extract_requirements_lines(self, soup) -> list[str]:
        section = soup.select_one("#requisitos-pane")
        if not section:
            return []

        return self._extract_clean_lines(
            section,
            title=None,
            remove_direct_divs=True,
        )

    def _extract_clean_lines(self, element, *, title: Optional[str], remove_direct_divs: bool) -> list[str]:
        cloned = self.parse_html(str(element))
        root = cloned.find(getattr(element, "name", None)) if getattr(element, "name", None) else None
        if not root:
            return []

        if remove_direct_divs:
            for child in list(root.find_all("div", recursive=False)):
                child.decompose()

        for selector in ("script", "style", "hr", "button", ".btn", ".d-lg-none", ".text-muted"):
            for node in root.select(selector):
                node.decompose()

        text = root.get_text("\n", strip=True)
        title_token = self._normalize_token(title or "") if title else ""
        lines: list[str] = []
        seen: set[str] = set()

        for raw_line in text.splitlines():
            line = self._sanitize_line(raw_line)
            if not line:
                continue

            normalized_line = self._normalize_token(line)
            if not normalized_line:
                continue
            if normalized_line == title_token:
                continue
            if line.startswith("#"):
                continue
            if self._is_noise_line(line):
                continue
            if normalized_line in seen:
                continue

            seen.add(normalized_line)
            lines.append(line)

        return lines

    def _format_about_section(self, lines: list[str]) -> Optional[str]:
        cleaned_lines = [
            line for line in lines
            if self._normalize_token(line) not in {"sobre a vaga"}
        ]
        if not cleaned_lines:
            return None

        marker_index = next(
            (
                index for index, line in enumerate(cleaned_lines)
                if self._normalize_token(line) == "o que voce vai fazer"
            ),
            None,
        )

        parts: list[str] = []
        if marker_index is None:
            return self._join_sentence_lines(cleaned_lines)

        intro_lines = cleaned_lines[:marker_index]
        task_lines = cleaned_lines[marker_index + 1:]

        if intro_lines:
            parts.append(self._join_sentence_lines(intro_lines))
        if task_lines:
            parts.append(f"O que você vai fazer: {self._join_list_lines(task_lines)}.")

        return " ".join(part for part in parts if part) or None

    def _format_requirements_section(self, lines: list[str]) -> Optional[str]:
        cleaned_lines = [line for line in lines if not self._is_metadata_line(line)]
        if not cleaned_lines:
            return None

        heading = None
        first_token = self._normalize_token(cleaned_lines[0])
        if first_token in {"conhecimentos esperados", "requisitos", "requisitos obrigatorios"}:
            heading = cleaned_lines[0]
            cleaned_lines = cleaned_lines[1:]

        if not cleaned_lines:
            return None

        requirement_items: list[str] = []
        trailing_sentences: list[str] = []

        for line in cleaned_lines:
            if self._looks_like_sentence(line):
                trailing_sentences.append(self._ensure_terminal_punctuation(line))
            else:
                requirement_items.append(line)

        parts: list[str] = []
        if requirement_items:
            label = heading or "Requisitos"
            parts.append(f"{label}: {self._join_list_lines(requirement_items)}.")
        elif heading:
            parts.append(self._ensure_terminal_punctuation(heading))

        if trailing_sentences:
            parts.append(" ".join(trailing_sentences))

        return " ".join(part for part in parts if part) or None

    @classmethod
    def _sanitize_text(cls, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        value = html.unescape(text)
        value = value.replace("\u00a0", " ").replace("\u200b", " ")
        value = cls.EMOJI_PATTERN.sub(" ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value or None

    @classmethod
    def _sanitize_line(cls, line: str) -> Optional[str]:
        text = cls._sanitize_text(line)
        if not text:
            return None

        text = text.replace("…", "...")
        text = re.sub(r"^[\-\|\u2022\u2023\u2043\u2219\u25E6\u00B7]+\s*", "", text)
        text = re.sub(r"\s*[\-\|]+\s*$", "", text)
        text = re.sub(r"\s+", " ", text).strip(" -|")
        return text or None

    @classmethod
    def _is_noise_line(cls, line: str) -> bool:
        for pattern in cls.DESCRIPTION_NOISE_PATTERNS:
            if re.match(pattern, line, flags=re.IGNORECASE):
                return True
        return False

    @classmethod
    def _is_metadata_line(cls, line: str) -> bool:
        token = cls._normalize_token(line)
        if token.startswith("nivel "):
            return True
        if token.startswith("contratacao "):
            return True
        if token.startswith("codigo "):
            return True
        return False

    @staticmethod
    def _looks_like_sentence(line: str) -> bool:
        return line.endswith((".", "!", "?")) or len(line.split()) >= 8

    @staticmethod
    def _ensure_terminal_punctuation(text: str) -> str:
        if not text:
            return ""
        if text.endswith((".", "!", "?", ":")):
            return text
        return f"{text}."

    def _join_sentence_lines(self, lines: list[str]) -> str:
        return " ".join(self._ensure_terminal_punctuation(line) for line in lines if line)

    @staticmethod
    def _join_list_lines(lines: list[str]) -> str:
        return "; ".join(line.strip(" ;.") for line in lines if line)

    def _clean_description_text(self, text: Optional[str]) -> Optional[str]:
        lines = [
            line for line in (
                self._sanitize_line(raw_line)
                for raw_line in (text or "").splitlines()
            )
            if line and not self._is_noise_line(line)
        ]
        if not lines:
            return None
        return self._join_sentence_lines(lines)

    def _extract_job_posting_payload(self, soup) -> dict:
        for node in soup.select('script[type="application/ld+json"]'):
            raw_json = node.get_text(strip=True)
            if not raw_json:
                continue
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            job_posting = self._find_job_posting(payload)
            if job_posting:
                return job_posting

        return {}

    def _find_job_posting(self, payload) -> Optional[dict]:
        if isinstance(payload, list):
            for item in payload:
                job_posting = self._find_job_posting(item)
                if job_posting:
                    return job_posting
            return None

        if not isinstance(payload, dict):
            return None

        payload_type = payload.get("@type")
        if isinstance(payload_type, list):
            if any(str(item).lower() == "jobposting" for item in payload_type):
                return payload
        elif str(payload_type).lower() == "jobposting":
            return payload

        graph = payload.get("@graph")
        if isinstance(graph, list):
            return self._find_job_posting(graph)

        return None

    @staticmethod
    def _extract_company_from_job_posting(job_posting: dict) -> Optional[str]:
        organization = job_posting.get("hiringOrganization")
        if isinstance(organization, dict):
            name = organization.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
        return None

    def _extract_salary_text_from_job_posting(self, job_posting: dict) -> Optional[str]:
        salary = job_posting.get("baseSalary")
        if not isinstance(salary, dict):
            return None

        value = salary.get("value")
        if not isinstance(value, dict):
            return None

        min_value = self._to_float(value.get("minValue"))
        max_value = self._to_float(value.get("maxValue"))

        if min_value in {None, 0} and max_value in {None, 0}:
            return "Salário a Combinar"

        if min_value and max_value:
            return f"{self._format_brl(min_value)} - {self._format_brl(max_value)}"
        if min_value:
            return self._format_brl(min_value)
        if max_value:
            return self._format_brl(max_value)
        return None

    @staticmethod
    def _to_float(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_brl(value: float) -> str:
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"

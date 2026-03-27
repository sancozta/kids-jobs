from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from adapters.outbound.scraping.telegram_scraper import TelegramScraper
from application.domain.entities.scraped_item import ScrapedItem
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


class TelegramJobsTIScraper(TelegramScraper):
    """Scraper de vagas remotas de TI publicadas em grupos/canais de Telegram."""

    TECH_KEYWORDS = (
        "desenvolvedor",
        "developer",
        "engenheiro",
        "engineer",
        "software",
        "backend",
        "back-end",
        "frontend",
        "front-end",
        "fullstack",
        "full stack",
        "mobile",
        "ios",
        "android",
        "react",
        "react native",
        "angular",
        "vue",
        "node",
        "nodejs",
        "python",
        "java",
        "golang",
        "go ",
        "php",
        "laravel",
        "django",
        "flask",
        "ruby",
        "rails",
        "devops",
        "sre",
        "cloud",
        "dados",
        "data engineer",
        "data scientist",
        "machine learning",
        "consultor",
        "sap",
        "abap",
        "pmo",
        "qa",
        "tester",
        "product engineer",
        "tech lead",
        "arquiteto de software",
        "ti",
    )
    REMOTE_KEYWORDS = ("remoto", "remote", "home office", "anywhere", "worldwide", "latam", "brazil")
    TITLE_PREFIXES = (
        "vaga",
        "cargo",
        "posição",
        "position",
        "opportunity",
        "oportunidade",
        "job",
    )
    COMPANY_PREFIXES = ("empresa", "cliente", "company", "contratante")
    LOCATION_PREFIXES = ("local", "localização", "location")
    IGNORE_LINE_PREFIXES = (
        "salário",
        "salary",
        "contrato",
        "contract",
        "modelo",
        "benefícios",
        "beneficios",
        "requisitos",
        "responsabilidades",
        "interessados",
        "interested",
        "contato",
        "candidate-se",
        "candidate se",
    )
    GENERIC_HEADER_PATTERNS = (
        "oportunidade de carreira",
        "novas oportunidades",
        "vagas ativas",
        "vagas abertas",
        "está pronto para",
        "voce esta pronto para",
        "junte-se",
        "junte se",
        "international remote opportunities",
        "olá, equipe do home office",
    )
    AGGREGATE_PATTERNS = (
        "diversas vagas",
        "novas vagas remotas",
        "vagas remotas",
        "participe de projetos remotos",
        "oportunidades remotas",
    )
    NON_COMPANY_TOKENS = {
        "remoto",
        "remote",
        "presencial",
        "hibrido",
        "híbrido",
        "clt",
        "pj",
        "freelancer",
        "freela",
        "temporario",
        "temporário",
        "whatsapp",
        "whats",
        "wpp",
        "mm",
        "fuso",
        "horario",
        "horário",
    }
    COMPANY_STOPWORDS = {
        "vaga",
        "vagas",
        "oferta",
        "oferece",
        "diversas",
        "home",
        "office",
        "remoto",
        "remote",
        "senior",
        "sênior",
        "junior",
        "júnior",
        "pleno",
        "area",
        "área",
        "tecnologia",
        "emprego",
        "empregos",
        "trabalho",
        "urgente",
        "projetos",
        "projeto",
        "ti",
        "na",
        "no",
        "de",
        "do",
        "da",
        "e",
        "em",
        "para",
        "com",
        "2024",
        "2025",
        "2026",
    }
    TITLE_URL_STOPWORDS = COMPANY_STOPWORDS | {
        "grupo",
        "jobs",
        "job",
        "oportunidades",
        "oficial",
    }
    UPPER_TOKENS = {"SAP", "PMO", "QA", "UOL", "CLT", "PJ", "TI", "AI", "ABAP", "CQA"}
    GENERIC_TITLE_PREFIXES = (
        "olá",
        "ola",
        "bom dia",
        "boa tarde",
        "boa noite",
        "urgente",
        "opportunity",
        "vem ser",
        "estamos com",
        "está com",
        "a consultoria",
    )
    EMOJI_RE = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA70-\U0001FAFF"
        "\u2600-\u26FF"
        "\u2700-\u27BF"
        "]+",
        flags=re.UNICODE,
    )
    BAD_LOCATION_TOKENS = {
        "junte",
        "cadastre",
        "manter",
        "vaga",
        "vagas",
        "oportunidade",
        "objetivo",
        "projeto",
        "remoto",
        "remote",
    }
    LOCATION_NOISE_TOKENS = {
        "atividade",
        "atividades",
        "beneficio",
        "beneficios",
        "benefício",
        "benefícios",
        "comunicar",
        "comunicacao",
        "comunicação",
        "conhecimento",
        "conhecimentos",
        "experiencia",
        "experiência",
        "procedimento",
        "procedimentos",
        "requisito",
        "requisitos",
        "responsabilidade",
        "responsabilidades",
        "solicitada",
        "solicitadas",
        "solicitado",
        "solicitados",
        "suporte",
        "usuario",
        "usuário",
        "usuarios",
        "usuários",
    }

    @staticmethod
    def get_default_config() -> ScraperConfig:
        return ScraperConfig(
            metadata=ScraperMetadata(
                name="telegram_jobs_ti",
                display_name="Telegram Jobs TI",
                description="Captura vagas remotas de TI em grupos e canais do Telegram",
                category=ScrapingCategory.JOBS,
                source_type=SourceType.TELEGRAM,
                version="1.0.0",
            ),
            base_url="https://t.me",
            enabled=True,
            timeout=45,
            rate_limit_delay=0.0,
            max_items_per_run=100,
            extra_config={
                "channels": [],
                "lookback_limit": 120,
                "ocr_enabled": True,
                "ocr_languages": "por+eng",
            },
        )

    def scrape(self) -> list[ScrapedItem]:
        channels = self._telegram_channels()
        if not channels:
            self.logger.warning("Nenhum canal configurado em SCRAPING_TELEGRAM_JOBS_TI_CHANNELS")
            return []

        client = self._ensure_client_started()
        if client is None:
            return []

        items: list[ScrapedItem] = []
        try:
            for channel_ref in channels:
                last_seen_id = 0
                current_entity = None
                try:
                    for entity, message in self._iter_channel_messages(client, channel_ref):
                        current_entity = entity
                        message_id = int(getattr(message, "id", 0) or 0)
                        last_seen_id = max(last_seen_id, message_id)
                        item = self._message_to_item(entity, message)
                        if item:
                            items.append(item)
                        if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                            break
                except Exception:
                    self.logger.exception("Falha ao processar canal Telegram %s", channel_ref)
                finally:
                    if last_seen_id > 0:
                        chat_id = str(getattr(current_entity, "id", channel_ref))
                        self._save_offset(chat_id, last_seen_id)
                if self.config.max_items_per_run and len(items) >= self.config.max_items_per_run:
                    break
        finally:
            self._shutdown_client()
        return items

    def scrape_url(self, url: str) -> Optional[ScrapedItem]:
        normalized = self._normalize_scrape_url(url)
        self._reset_scrape_url_diagnostics(url=normalized or url)
        if not normalized.startswith("telegram://"):
            return None

        match = re.match(r"^telegram://(-?\d+)/(\d+)$", normalized)
        if not match:
            return None
        chat_id, message_id = match.group(1), int(match.group(2))

        client = self._ensure_client_started()
        if client is None:
            return None

        try:
            entity = self._resolve_entity_for_chat_id(client, chat_id)
            if entity is None:
                return None
            message = self._run_async(client.get_messages(entity, ids=message_id))
            if not message:
                self._mark_scrape_url_missing(
                    reason="Mensagem Telegram não encontrada",
                    url=normalized,
                )
                return None
            return self._message_to_item(entity, message)
        except Exception as exc:
            message_text = str(exc).lower()
            if any(token in message_text for token in ("not found", "não encontrado", "nao encontrado", "could not find", "message not found")):
                self._mark_scrape_url_missing(
                    reason="Mensagem Telegram não encontrada",
                    url=normalized,
                )
                return None
            raise
        finally:
            self._shutdown_client()

    def _message_to_item(self, entity, message) -> Optional[ScrapedItem]:
        body_text = self._extract_message_text(message)
        ocr_text = None
        body_is_candidate = self._is_candidate_job(body_text)
        should_try_ocr = self._message_has_image(message) and (not body_text or not body_is_candidate)
        if should_try_ocr:
            image_bytes = self._download_message_media_bytes(self._client, message)
            ocr_text = self._ocr_image_bytes(image_bytes)
        analysis_text = self._compose_text(body_text, ocr_text)
        if not analysis_text:
            return None
        if not self._is_candidate_job(analysis_text):
            return None
        if self._is_aggregate_post(analysis_text):
            return None

        description_text = self._build_description_text(body_text, ocr_text, fallback_text=analysis_text)
        parsing_text = description_text or analysis_text

        header_title, header_company, header_city, header_state = self._extract_header_metadata(parsing_text)
        links = self._extract_urls(analysis_text)
        title = header_title or self._extract_title(parsing_text, links)
        company = header_company or self._extract_company(analysis_text, links, title)
        title = self._refine_title(title, parsing_text, links, company)
        salary_text = self._extract_salary_text(analysis_text)
        contact_email = self._extract_email(analysis_text)
        contact_phone = self._extract_phone(analysis_text)
        city, state = self._extract_location(parsing_text)
        city = header_city or city
        state = header_state or state
        public_link = self._build_public_message_link(entity, int(message.id))
        if public_link and public_link not in links:
            links.append(public_link)
        dedupe_key = self._build_dedupe_key(title=title, company=company, text=analysis_text, links=links)
        canonical_url = self._build_canonical_message_url(entity, int(message.id))

        message_dt = getattr(message, "date", None)
        if isinstance(message_dt, datetime):
            if message_dt.tzinfo is None:
                message_dt = message_dt.replace(tzinfo=timezone.utc)
            telegram_posted_at = message_dt.astimezone(timezone.utc).isoformat()
        else:
            telegram_posted_at = None

        scraped_data = {
            "title": title,
            "description": description_text,
            "currency": "BRL",
            "city": city,
            "state": state,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "links": links,
            "attributes": {
                "company": company,
                "salary_range": salary_text,
                "seniority": self._infer_seniority(analysis_text),
                "contract_type": self._infer_contract_type(analysis_text),
                "work_model": self._infer_work_model(analysis_text),
                "experience_years": self._extract_experience_years(analysis_text),
                "telegram_chat": getattr(entity, "title", None) or getattr(entity, "username", None),
                "telegram_chat_id": str(getattr(entity, "id", "")) or None,
                "telegram_message_id": int(message.id),
                "telegram_posted_at": telegram_posted_at,
                "source_message_type": self._detect_message_type(message, ocr_text),
                "ocr_used": bool(ocr_text),
                "telegram_public_url": public_link,
                "telegram_canonical_url": canonical_url,
                "dedupe_key": dedupe_key,
            },
        }

        return self.build_scraped_item(
            url=canonical_url,
            scraped_data=scraped_data,
        )

    @staticmethod
    def _extract_message_text(message) -> str:
        parts: list[str] = []
        for attr in ("message", "text", "raw_text"):
            value = getattr(message, attr, None)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                break
        if getattr(message, "entities", None):
            with_links = []
            for entity in getattr(message, "entities", []) or []:
                url = getattr(entity, "url", None)
                if isinstance(url, str) and url.strip():
                    with_links.append(url.strip())
            if with_links:
                parts.append("\n".join(with_links))
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _message_has_image(message) -> bool:
        if getattr(message, "photo", None) is not None:
            return True
        document = getattr(message, "document", None)
        if document is None:
            return False
        mime_type = getattr(document, "mime_type", None)
        return isinstance(mime_type, str) and mime_type.startswith("image/")

    @staticmethod
    def _compose_text(body_text: str, ocr_text: Optional[str]) -> str:
        chunks = []
        if body_text:
            chunks.append(TelegramJobsTIScraper._normalize_multiline_text(body_text))
        if ocr_text:
            chunks.append(TelegramJobsTIScraper._normalize_multiline_text(ocr_text))
        text = "\n\n".join(chunks)
        return text.strip()

    @classmethod
    def _is_aggregate_post(cls, text: str) -> bool:
        normalized = text.lower()
        if any(pattern in normalized for pattern in cls.GENERIC_HEADER_PATTERNS):
            return True
        if any(pattern in normalized for pattern in cls.AGGREGATE_PATTERNS):
            return True
        if len(re.findall(r"https?://", text, flags=re.IGNORECASE)) >= 3:
            return True
        role_lines = 0
        for raw_line in text.splitlines():
            line = cls._clean_line(raw_line)
            normalized_line = line.lower()
            if any(keyword in normalized_line for keyword in cls.TECH_KEYWORDS):
                role_lines += 1
        return role_lines >= 4

    @classmethod
    def _is_candidate_job(cls, text: str) -> bool:
        normalized = (text or "").lower()
        tech_hit = any(keyword in normalized for keyword in cls.TECH_KEYWORDS)
        remote_hit = any(keyword in normalized for keyword in cls.REMOTE_KEYWORDS)
        return tech_hit and remote_hit

    @classmethod
    def _extract_title(cls, text: str, links: Optional[list[str]] = None) -> str:
        lines = [cls._clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        for line in lines:
            normalized = line.lower()
            if normalized.startswith(("http://", "https://")):
                continue
            if any(pattern in normalized for pattern in cls.GENERIC_HEADER_PATTERNS):
                continue
            like_role = re.search(
                r"(?:atuação como|atuacao como|vaga abaixo[:\s-]*|posição para|position for)\s+(.+?)(?:[.!]|$)",
                line,
                flags=re.IGNORECASE,
            )
            if like_role:
                return cls._format_title_candidate(like_role.group(1))
            for prefix in cls.TITLE_PREFIXES:
                if normalized.startswith(prefix + ":"):
                    candidate = cls._clean_line(line.split(":", 1)[1])
                    if candidate:
                        return cls._format_title_candidate(candidate)
                if normalized.startswith(prefix + " "):
                    candidate = cls._clean_line(line[len(prefix):])
                    candidate = re.split(r"\s+[–—-]\s+", candidate)[0].strip()
                    if candidate:
                        return cls._format_title_candidate(candidate)
            if any(normalized.startswith(prefix) for prefix in cls.IGNORE_LINE_PREFIXES):
                continue
            if any(keyword in normalized for keyword in cls.TECH_KEYWORDS) and len(line) >= 6:
                return cls._format_title_candidate(line)
        role_candidate = cls._extract_role_candidate(text)
        if role_candidate:
            return cls._format_title_candidate(role_candidate)
        if links:
            link_title = cls._derive_title_from_links(links)
            if link_title:
                return cls._format_title_candidate(link_title)
        fallback = lines[0] if lines else ""
        if fallback.lower().startswith(("http://", "https://")) and links:
            fallback = cls._derive_title_from_links(links) or ""
        return cls._format_title_candidate(fallback) if fallback else "Vaga de TI remota"

    @classmethod
    def _extract_company(cls, text: str, links: Optional[list[str]] = None, title: Optional[str] = None) -> Optional[str]:
        for line in text.splitlines():
            cleaned = cls._clean_line(line)
            normalized = cleaned.lower()
            for prefix in cls.COMPANY_PREFIXES:
                if normalized.startswith(prefix + ":"):
                    return cls._clean_line(cleaned.split(":", 1)[1])
            consultoria_match = re.search(r"\bconsultoria\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,2})\b", cleaned, flags=re.IGNORECASE)
            if consultoria_match:
                company = cls._clean_company(consultoria_match.group(1))
                if company:
                    return company
            brand_call_match = re.search(r"\bvem\s+(?:ser|para)\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,2})\b", cleaned, flags=re.IGNORECASE)
            if brand_call_match:
                company = cls._clean_company(brand_call_match.group(1))
                if company:
                    return company
            group_match = re.search(r"\bgrupo\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,3})\b", cleaned, flags=re.IGNORECASE)
            if group_match:
                company = cls._clean_company(group_match.group(1))
                if company:
                    return company
            contextual_match = re.search(
                r"\b(?:aqui na|na|no|para a|para o)\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,4})\b",
                cleaned,
                flags=re.IGNORECASE,
            )
            if contextual_match:
                company = cls._clean_company(contextual_match.group(1))
                if company:
                    return company
        first_line = cls._clean_line(text.splitlines()[0]) if text.splitlines() else ""
        if first_line:
            parts = [cls._clean_line(part) for part in re.split(r"\s+[–—-]\s+", first_line) if cls._clean_line(part)]
            if len(parts) >= 2:
                company_candidate = parts[-1]
                if not cls._looks_like_location(company_candidate):
                    return company_candidate.title() if not company_candidate.isupper() else company_candidate
            first_line_company = re.search(
                r"\bna\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,4})\b",
                first_line,
                flags=re.IGNORECASE,
            )
            if first_line_company:
                company = cls._clean_company(first_line_company.group(1))
                if company:
                    return company
        company_match = re.search(
            r"(?im)^\s*(?:a|o)?\s*([A-Z][A-Za-z0-9&.\- ]{2,60})\s+(?:busca|esta|está|procura|quer|abre|abriu|contrata)\b",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if company_match:
            return cls._clean_company(company_match.group(1))
        email_match = re.search(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", text)
        if email_match:
            domain = email_match.group(1).split(".")[0]
            if domain and domain.lower() not in {"gmail", "hotmail", "outlook", "yahoo"}:
                return cls._format_brand(domain.replace("-", " ").replace("_", " "))
        if title:
            title_company = cls._extract_company_from_title(title)
            if title_company:
                return title_company
        if links:
            for link in links:
                company = cls._company_from_url(link)
                if company:
                    return company
        return None

    @classmethod
    def _extract_header_metadata(
        cls,
        text: str,
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        first_line = ""
        for raw_line in text.splitlines():
            cleaned = cls._clean_line(raw_line)
            if cleaned:
                first_line = cleaned
                break
        if not first_line:
            return None, None, None, None

        line_no_emoji = cls._strip_visual_noise(first_line)
        city, state = cls._extract_location(line_no_emoji)
        parts = [cls._clean_line(part) for part in re.split(r"\s+[–—-]\s+", line_no_emoji) if cls._clean_line(part)]
        title = None
        company = None
        if parts:
            title_candidate = parts[0]
            title_candidate = re.sub(r"^(?:vaga|cargo|posição|position|oportunidade|job)\s*:?[\s-]*", "", title_candidate, flags=re.IGNORECASE)
            title = cls._format_title_candidate(title_candidate) if title_candidate else None
        if len(parts) >= 2:
            trailing = [part for part in parts[1:] if not cls._is_location_segment(part)]
            if trailing:
                company = cls._clean_company(trailing[-1])
        return title or None, company or None, city, state

    @classmethod
    def _extract_location(cls, text: str) -> tuple[Optional[str], Optional[str]]:
        patterns = (
            r"(?:presencial\s+em|em|local(?:ização)?[:\s]|cidade[:\s]|atuação[:\s])\s*([A-Za-zÀ-ÿ'`\-\s]{2,70})\s*/\s*([A-Za-z]{2})\b",
            r"(?:presencial\s+em|em|local(?:ização)?[:\s]|cidade[:\s]|atuação[:\s])\s*([A-Za-zÀ-ÿ'`\-\s]{2,70})\s+-\s+([A-Za-z]{2})\b",
            r"\b([A-Za-zÀ-ÿ'`\-\s]{2,70})\s*/\s*([A-Za-z]{2})\b",
            r"\b([A-Za-zÀ-ÿ'`\-\s]{2,70})\s+-\s+([A-Za-z]{2})\b",
        )
        for raw_line in text.splitlines():
            line = cls._clean_line(raw_line)
            if not line:
                continue
            for pattern in patterns:
                match = re.search(pattern, line, flags=re.IGNORECASE)
                if not match:
                    continue
                city_candidate = cls._normalize_location_candidate(match.group(1)).title()
                state_candidate = match.group(2).upper()
                if cls._looks_like_location(city_candidate) and state_candidate in cls.BRAZIL_UF:
                    return city_candidate, state_candidate
        return None, None

    @classmethod
    def _looks_like_location(cls, value: str) -> bool:
        normalized = cls._normalize_location_candidate(value).lower()
        if not normalized or normalized in cls.BAD_LOCATION_TOKENS:
            return False
        tokens = re.findall(r"[a-zà-ÿ']+", normalized)
        if not tokens:
            return False
        if len(normalized) > 45:
            return False
        if len(tokens) > 6:
            return False
        if any(token in cls.LOCATION_NOISE_TOKENS for token in tokens):
            return False
        if normalized in cls.BRAZIL_STATE_NAME_TO_UF:
            return False
        if normalized.upper() in cls.BRAZIL_UF:
            return False
        return True

    @classmethod
    def _is_location_segment(cls, value: str) -> bool:
        city, state = cls._extract_location(value)
        return bool(city and state)

    @classmethod
    def _clean_company(cls, value: str) -> Optional[str]:
        company = cls._clean_line(value)
        company = re.sub(r"^(?:empresa|cliente|company|contratante)\s*:?\s*", "", company, flags=re.IGNORECASE)
        email_match = re.search(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})", company, flags=re.IGNORECASE)
        if email_match:
            domain = email_match.group(1).split(".")[0]
            if domain.lower() not in {"gmail", "hotmail", "outlook", "yahoo"}:
                company = domain.replace("-", " ").replace("_", " ")
        company = re.split(
            r"\b(?:atuação|atuacao|contratação|contratacao|requisitos?|responsabilidades|modelo|modalidade|com\s+cliente|cliente|fuso|horário|horario)\b",
            company,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        company = re.sub(r"\b(?:remoto|remote|presencial|hibrido|híbrido|clt|pj)\b", "", company, flags=re.IGNORECASE)
        company = re.sub(r"\b(?:whatsapp|zap|bairro|email|cv|curr[íi]culo|enviar|mandar|link)\b.*$", "", company, flags=re.IGNORECASE)
        company = re.sub(r"\s{2,}", " ", company).strip(" -|:")
        if company.lower() in cls.NON_COMPANY_TOKENS:
            return None
        if company.lower().startswith("www."):
            company = company[4:]
        company = re.sub(r"\.(com|com\.br|io|ai|dev|tech|pt|net|org)$", "", company, flags=re.IGNORECASE)
        if "http" in company.lower() or "@" in company:
            return None
        if len(company.split()) > 6:
            return None
        if len(company.strip()) < 3:
            return None
        return cls._format_brand(company) if company else None

    @classmethod
    def _normalize_location_candidate(cls, value: str) -> str:
        candidate = cls._clean_line(value)
        candidate = re.split(r"\s+[–—-]\s+", candidate)[-1]
        candidate = re.sub(
            r"^(?:presencial\s+em|em|na|no|local(?:ização)?|cidade|atuação)\s*:?\s*",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r"\s{2,}", " ", candidate)
        return candidate.strip(" -|:/")

    @classmethod
    def _format_title_candidate(cls, value: str) -> str:
        cleaned = cls._strip_visual_noise(value or "")
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -|:")
        if not cleaned:
            return "Vaga de TI remota"
        letters = [ch for ch in cleaned if ch.isalpha()]
        uppercase_ratio = (
            sum(1 for ch in letters if ch.isupper()) / len(letters)
            if letters
            else 0
        )
        if uppercase_ratio >= 0.7:
            return cls._format_brand(cleaned.title())
        return cls._format_brand(cleaned[0].upper() + cleaned[1:])

    @classmethod
    def _refine_title(cls, title: str, text: str, links: list[str], company: Optional[str]) -> str:
        candidate = cls._strip_visual_noise(title or "")
        role_candidate = cls._extract_role_candidate(text)
        if candidate.lower().startswith(("http://", "https://")):
            candidate = role_candidate or cls._derive_title_from_links(links) or "Vaga de TI remota"
        normalized_candidate = candidate.lower()
        if (
            any(normalized_candidate.startswith(prefix) for prefix in cls.GENERIC_TITLE_PREFIXES)
            or len(candidate) > 110
            or "linkedin" in normalized_candidate
        ) and role_candidate:
            candidate = role_candidate
        candidate = re.sub(r"\b(?:100%\s*)?(?:remoto|remote|home office|híbrido|hibrido)\b", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\b20\d{2}\b", "", candidate)
        if company:
            candidate = re.sub(rf"\bna\s+{re.escape(company)}\b", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(rf"\b{re.escape(company)}\b", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s{2,}", " ", candidate).strip(" -|:/")
        return cls._format_title_candidate(candidate or "Vaga de TI remota")

    @staticmethod
    def _normalize_link(value: str) -> str:
        normalized = value.strip()
        normalized = re.sub(r"[?#].*$", "", normalized)
        return normalized.rstrip("/")

    @classmethod
    def _build_dedupe_key(cls, *, title: str, company: Optional[str], text: str, links: list[str]) -> str:
        external_links = [
            cls._normalize_link(link)
            for link in links
            if link and "t.me/" not in link and not link.startswith("telegram://")
        ]
        if external_links:
            return f"link:{external_links[0]}"
        fingerprint = "|".join(
            [
                cls._normalize_token(title or ""),
                cls._normalize_token(company or ""),
                cls._normalize_token((text or "")[:280]),
            ]
        )
        return "text:" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _extract_salary_text(text: str) -> Optional[str]:
        for line in text.splitlines():
            cleaned = line.strip()
            normalized = cleaned.lower()
            if normalized.startswith(("salário", "salario", "salary", "faixa")):
                return cleaned.split(":", 1)[1].strip() if ":" in cleaned else cleaned
        match = re.search(r"(R\$\s*[0-9\.,kK]+(?:\s*(?:a|até|to|-)\s*R?\$?\s*[0-9\.,kK]+)?)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"((?:USD|US\$|EUR|€)\s*[0-9\.,kK]+(?:\s*(?:a|até|to|-)\s*(?:USD|US\$|EUR|€)?\s*[0-9\.,kK]+)?)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.IGNORECASE)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        match = re.search(r"(?:\+?\d{1,3}\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}", text)
        return match.group(0).strip() if match else None

    @classmethod
    def _clean_line(cls, value: str) -> str:
        line = cls._strip_visual_noise(value or "")
        line = re.sub(r"^[\s\-–—•*|]+", "", line)
        line = re.sub(r"\s+", " ", line)
        return line.strip(" -|:")

    @classmethod
    def _strip_visual_noise(cls, value: str) -> str:
        text = cls.EMOJI_RE.sub(" ", value or "")
        text = text.replace("\u00a0", " ")
        text = text.replace("*", " ")
        text = re.sub(r"[👨👩💻📢🔥✅❌📝•▪️▫️►▶]+", " ", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    @classmethod
    def _normalize_multiline_text(cls, value: str) -> str:
        text = cls._strip_visual_noise(value or "")
        text = text.replace("\r", "\n").replace("\t", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _build_description_text(cls, body_text: str, ocr_text: Optional[str], *, fallback_text: str) -> str:
        structured_ocr = cls._format_structured_ocr_text(ocr_text)
        if not structured_ocr:
            return fallback_text

        body_fragment = cls._sanitize_caption_for_description(body_text)
        if body_fragment:
            return f"{structured_ocr}\n\n{body_fragment}".strip()
        return structured_ocr

    @classmethod
    def _format_structured_ocr_text(cls, ocr_text: Optional[str]) -> Optional[str]:
        if not ocr_text:
            return None

        normalized = cls._normalize_multiline_text(ocr_text)
        if not normalized:
            return None

        normalized = re.sub(
            r"\s+(?=(?:Cidade|N[ií]vel|Dura(?:ção|cao)|Idioma|Requisitos|OBS|Observa(?:ções|coes))\s*:)",
            "\n",
            normalized,
            flags=re.IGNORECASE,
        )
        lines = [cls._clean_line(line) for line in normalized.splitlines()]
        lines = [line for line in lines if line]
        if len(lines) < 2:
            return None

        title = None
        metadata: list[str] = []
        requirements: list[str] = []
        observations: list[str] = []
        extras: list[str] = []
        section: Optional[str] = None
        label_hits = 0

        for index, line in enumerate(lines):
            label_match = cls._parse_structured_ocr_label(line)
            if index == 0 and label_match is None:
                title = line
                continue

            if label_match is not None:
                label, value = label_match
                label_hits += 1
                if label in {"Cidade", "Nível", "Duração", "Idioma"}:
                    metadata.append(f"{label}: {value}" if value else f"{label}:")
                    section = None
                    continue
                if label == "Requisitos":
                    section = "requirements"
                    if value:
                        requirements.append(cls._normalize_ocr_bullet(value))
                    continue
                if label == "Observações":
                    section = "observations"
                    if value:
                        observations.append(value)
                    continue

            if section == "requirements":
                requirements.append(cls._normalize_ocr_bullet(line))
            elif section == "observations":
                observations.append(line)
            else:
                extras.append(line)

        if not title or label_hits < 2:
            return None

        parts = [title]
        parts.extend(metadata)
        if extras:
            parts.append("")
            parts.extend(extras)
        if requirements:
            parts.append("")
            parts.append("Requisitos:")
            parts.extend(f"- {entry}" for entry in requirements if entry)
        if observations:
            parts.append("")
            parts.append("Observações:")
            parts.extend(observations)
        return "\n".join(part for part in parts if part is not None).strip()

    @classmethod
    def _parse_structured_ocr_label(cls, line: str) -> Optional[tuple[str, str]]:
        match = re.match(
            r"^(cidade|n[ií]vel|dura(?:ção|cao)|idioma|requisitos|obs|observa(?:ções|coes))(?:\s*:\s*(.*))?$",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        raw_label = match.group(1).lower()
        value = cls._clean_line(match.group(2) or "")
        if raw_label == "cidade":
            return "Cidade", value
        if raw_label in {"nível", "nivel"}:
            return "Nível", value
        if raw_label in {"duração", "duracao"}:
            return "Duração", value
        if raw_label == "idioma":
            return "Idioma", value
        if raw_label == "requisitos":
            return "Requisitos", value
        return "Observações", value

    @classmethod
    def _normalize_ocr_bullet(cls, value: str) -> str:
        bullet = cls._clean_line(value)
        bullet = re.sub(r"^[\-•·▪▫]+\s*", "", bullet)
        return bullet.strip(" ;")

    @classmethod
    def _sanitize_caption_for_description(cls, body_text: str) -> Optional[str]:
        if not body_text:
            return None

        kept_lines: list[str] = []
        for raw_line in body_text.splitlines():
            line = cls._clean_line(raw_line)
            if not line:
                continue
            normalized = line.lower()
            urls = [match.group(0).rstrip(".,;") for match in re.finditer(r"https?://[^\s)\]>]+", line, flags=re.IGNORECASE)]
            email = cls._extract_email(line)

            if any(pattern in normalized for pattern in ("estamos a crescer", "vem para", "envie seu cv", "envie seu currículo", "envie seu curriculo")):
                if email:
                    kept_lines.append(f"Contato: {email}")
                kept_lines.extend(urls)
                continue

            kept_lines.append(line)

        sanitized = "\n".join(dict.fromkeys(kept_lines)).strip()
        return sanitized or None

    @classmethod
    def _extract_role_candidate(cls, text: str) -> Optional[str]:
        normalized = cls._clean_line(text)
        patterns = (
            r"\b(consultor(?:a)?\s+sap\s+[a-z]{1,5})\b",
            r"\b(consultor(?:a)?\s+[a-z0-9+#./ -]{2,30})\b",
            r"\b(analista\s+[a-z0-9+#./ -]{2,35})\b",
            r"\b(desenvolvedor(?:a)?\s+[a-z0-9+#./ -]{2,35})\b",
            r"\b(mobile engineer(?:\s*\([^)]+\))?)\b",
            r"\b(back[- ]?end engineer(?:\s*\([^)]+\))?)\b",
            r"\b(front[- ]?end engineer(?:\s*\([^)]+\))?)\b",
            r"\b(full[- ]?stack engineer(?:\s*\([^)]+\))?)\b",
            r"\b(project manager|product manager|tech lead|data engineer|data scientist)\b",
            r"\b(pmo)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                candidate = re.split(r"\s+(?:requisitos?|must-haves?|must have|inicio|início|duração|duracao|link|candidate-se|candidatar)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
                candidate = re.sub(r"\b(?:100%\s*)?(?:remoto|remote|home office|híbrido|hibrido)\b", "", candidate, flags=re.IGNORECASE)
                candidate = re.sub(r"\b20\d{2}\b", "", candidate)
                return cls._clean_line(candidate)
        return None

    @classmethod
    def _extract_company_from_title(cls, title: str) -> Optional[str]:
        cleaned = cls._clean_line(title)
        match = re.search(r"\bna\s+([A-Z][A-Za-z0-9.&/\-]+(?:\s+[A-Z][A-Za-z0-9.&/\-]+){0,3})\b", cleaned, flags=re.IGNORECASE)
        if match:
            return cls._clean_company(match.group(1))
        return None

    @classmethod
    def _company_from_url(cls, url: str) -> Optional[str]:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = unquote(parsed.path or "").strip("/")
        segments = [segment for segment in path.split("/") if segment]

        if "jobs.quickin.io" in host and segments:
            return cls._clean_company(segments[0].replace("-", " ").replace("_", " "))
        if "work.vetto.ai" in host:
            return "Vetto"
        if "vagasdeempregoce.com" in host and segments:
            slug = segments[-1].lower()
            if slug.startswith("grupo-"):
                company_slug = slug.split("-oferta", 1)[0].replace("grupo-", "", 1)
                return cls._clean_company(company_slug.replace("-", " "))
            tokens = [token for token in slug.split("-") if token and token not in cls.COMPANY_STOPWORDS]
            role_cut_tokens = {
                "desenvolvedor", "desenvolvedora", "analista", "consultor", "consultora",
                "engenheiro", "engenheira", "backend", "frontend", "fullstack", "full", "stack",
                "java", "python", "react", "node", "mobile", "engineer", "cqa",
            }
            trailing: list[str] = []
            for token in tokens:
                if token in role_cut_tokens:
                    trailing = []
                    continue
                trailing.append(token)
            if trailing:
                return cls._clean_company(" ".join(trailing))
        return None

    @classmethod
    def _derive_title_from_links(cls, links: list[str]) -> Optional[str]:
        for link in links:
            parsed = urlparse(link)
            host = parsed.netloc.lower()
            path = unquote(parsed.path or "").strip("/")
            segments = [segment for segment in path.split("/") if segment]
            if "vagasdeempregoce.com" in host and segments:
                slug = segments[-1].lower()
                title_tokens = [
                    token for token in slug.split("-")
                    if token and token not in cls.TITLE_URL_STOPWORDS
                ]
                if title_tokens:
                    return " ".join(title_tokens)
            if "lnkd.in" in host:
                continue
        return None

    @classmethod
    def _format_brand(cls, value: str) -> str:
        tokens = re.split(r"(\s+)", value or "")
        formatted: list[str] = []
        for token in tokens:
            stripped = re.sub(r"[^A-Za-z0-9]", "", token)
            if not stripped:
                formatted.append(token)
                continue
            upper = stripped.upper()
            if upper in cls.UPPER_TOKENS:
                formatted.append(re.sub(re.escape(stripped), upper, token, flags=re.IGNORECASE))
                continue
            if stripped.isupper() and len(stripped) > 1:
                formatted.append(token.upper())
                continue
            if "-" in token:
                parts = []
                for part in token.split("-"):
                    raw = re.sub(r"[^A-Za-z0-9]", "", part)
                    if raw.isupper() and len(raw) > 1:
                        parts.append(part.upper())
                    else:
                        parts.append(part.capitalize() if part else part)
                formatted.append("-".join(parts))
                continue
            formatted.append(token.capitalize() if token.islower() else token)
        return "".join(formatted).strip()

    @classmethod
    def _infer_seniority(cls, text: str) -> Optional[str]:
        normalized = text.lower()
        if any(token in normalized for token in ("sênior", "senior", "sr")):
            return "senior"
        if any(token in normalized for token in ("pleno", "mid-level", "mid level")):
            return "pleno"
        if any(token in normalized for token in ("júnior", "junior", "jr")):
            return "junior"
        if "estágio" in normalized or "estagio" in normalized:
            return "estagio"
        if "especialista" in normalized or "specialist" in normalized:
            return "especialista"
        if "lead" in normalized or "líder" in normalized or "lider" in normalized:
            return "lider"
        return None

    @classmethod
    def _infer_contract_type(cls, text: str) -> Optional[str]:
        normalized = text.lower()
        if "pj" in normalized or "pessoa jurídica" in normalized or "contractor" in normalized:
            return "pj"
        if "clt" in normalized:
            return "clt"
        if "freelancer" in normalized or "freela" in normalized:
            return "freelancer"
        if "temporário" in normalized or "temporario" in normalized:
            return "temporario"
        return None

    @classmethod
    def _infer_work_model(cls, text: str) -> Optional[str]:
        normalized = text.lower()
        if any(token in normalized for token in ("híbrido", "hibrido", "hybrid")):
            return "hibrido"
        if any(token in normalized for token in cls.REMOTE_KEYWORDS):
            return "remoto"
        if "presencial" in normalized or "on-site" in normalized or "onsite" in normalized:
            return "presencial"
        return None

    @staticmethod
    def _extract_experience_years(text: str) -> Optional[int]:
        match = re.search(r"(\d{1,2})\+?\s*(?:anos|years)", text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    @staticmethod
    def _detect_message_type(message, ocr_text: Optional[str]) -> Optional[str]:
        has_body = bool(getattr(message, "message", None) or getattr(message, "text", None) or getattr(message, "raw_text", None))
        has_image = TelegramJobsTIScraper._message_has_image(message)
        if has_image and has_body:
            return "mixed"
        if has_image:
            return "image"
        if has_body:
            return "text"
        return None

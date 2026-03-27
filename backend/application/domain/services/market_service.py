"""Market service for local jobs persistence and querying."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import logging
import re
from typing import Any, Optional

from application.domain.entities.market import Market
from application.domain.exceptions.domain_exceptions import (
    ConcurrencyConflictException,
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidEntityException,
)
from application.domain.services.category_service import CategoryService
from application.domain.services.source_service import SourceService
from application.ports.outbound.persistence.market_persistence_port import MarketPersistencePort

logger = logging.getLogger(__name__)


class MarketService:
    JOB_SALARY_TYPE_VALUES = {"anual", "mensal", "semanal", "diario", "horario", "outro"}
    PATCHABLE_FIELDS = {
        "source_id",
        "category_id",
        "url",
        "title",
        "description",
        "price",
        "currency",
        "location",
        "state",
        "city",
        "zip_code",
        "street",
        "contact_name",
        "contact_phone",
        "contact_email",
        "images",
        "videos",
        "documents",
        "links",
        "attributes",
    }

    def __init__(
        self,
        repository: MarketPersistencePort,
        source_service: Optional[SourceService] = None,
        category_service: Optional[CategoryService] = None,
    ):
        self.repository = repository
        self.source_service = source_service
        self.category_service = category_service

    @staticmethod
    def _normalize_description_text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None

        text = html.unescape(value)
        text = re.sub(r"[\u00a0\u1680\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]", " ", text)
        text = text.replace("\t", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(
            r"</?(?:p|div|li|ul|ol|strong|b|em|span|h[1-6]|section|article|header|footer|table|tr|td)\b[^>]*>",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        text = re.sub(r" *\n+ *", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.replace("\n", " ")
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text or None

    @staticmethod
    def _normalize_market_link(value: str) -> str:
        normalized = str(value or "").strip()
        normalized = re.sub(r"[?#].*$", "", normalized)
        return normalized.rstrip("/")

    @staticmethod
    def _normalize_job_salary_type(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized in MarketService.JOB_SALARY_TYPE_VALUES else None

    @staticmethod
    def _parse_salary_amount_token(token: str, *, suffix: Optional[str] = None) -> Optional[float]:
        raw = re.sub(r"[^\d,.\-]", "", token or "").strip()
        if not raw or raw in {"-", ".", ","}:
            return None

        normalized = raw
        if "," in raw and "." in raw:
            last_comma = raw.rfind(",")
            last_dot = raw.rfind(".")
            if last_comma > last_dot:
                decimal_digits = len(raw[last_comma + 1 :])
                normalized = raw.replace(".", "").replace(",", ".") if decimal_digits in {1, 2} else raw.replace(".", "").replace(",", "")
            else:
                decimal_digits = len(raw[last_dot + 1 :])
                normalized = raw.replace(",", "") if decimal_digits in {1, 2} else raw.replace(",", "").replace(".", "")
        elif "," in raw:
            decimal_digits = len(raw.split(",")[-1])
            normalized = raw.replace(",", ".") if decimal_digits in {1, 2} else raw.replace(",", "")
        elif "." in raw:
            decimal_digits = len(raw.split(".")[-1])
            normalized = raw if decimal_digits in {1, 2} else raw.replace(".", "")

        try:
            amount = float(normalized)
        except ValueError:
            return None

        suffix_token = (suffix or "").strip().lower()
        if suffix_token == "k":
            amount *= 1_000
        elif suffix_token == "m":
            amount *= 1_000_000
        return amount if amount > 0 else None

    @staticmethod
    def _extract_salary_amounts(value: str) -> list[float]:
        matches: list[float] = []
        pattern = re.compile(
            r"(?<![A-Za-z0-9])(?:r\$\s*|us\$\s*|\$\s*|usd\s*|brl\s*)?(\d[\d.,]*)(?:\s*([kKmM]))?(?![A-Za-z0-9])"
        )
        for match in pattern.finditer(value):
            amount = MarketService._parse_salary_amount_token(match.group(1), suffix=match.group(2))
            if amount is not None:
                matches.append(float(amount))
        return matches

    @staticmethod
    def _normalize_job_salary_range(value: Any) -> Optional[float]:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
            return numeric_value if numeric_value > 0 else None
        if not isinstance(value, str):
            return None

        amounts = MarketService._extract_salary_amounts(value.strip())
        return next((float(amount) for amount in amounts if amount > 0), None)

    @staticmethod
    def _sanitize_market_attributes(category_name: Optional[str], attributes: Any) -> dict:
        if not isinstance(attributes, dict):
            return {}

        sanitized = dict(attributes)
        normalized_category_name = (category_name or "").strip().upper()

        if normalized_category_name != "EMPREGOS":
            return sanitized

        salary_range = MarketService._normalize_job_salary_range(sanitized.get("salary_range"))
        if salary_range is None:
            sanitized.pop("salary_range", None)
            sanitized.pop("salary_type", None)
        else:
            sanitized["salary_range"] = salary_range
            normalized_salary_type = MarketService._normalize_job_salary_type(sanitized.get("salary_type"))
            if normalized_salary_type is None:
                sanitized.pop("salary_type", None)
            else:
                sanitized["salary_type"] = normalized_salary_type

        return sanitized

    def _resolve_category_name(self, category_id: Optional[int]) -> Optional[str]:
        if not category_id or not self.category_service:
            return None
        category = self.category_service.get_by_id(category_id)
        return category.name if category else None

    def _sanitize_market_item(self, item: Market, *, category_name: Optional[str] = None) -> Market:
        resolved_category_name = category_name or self._resolve_category_name(item.category_id)
        item.description = self._normalize_description_text(item.description)
        item.attributes = self._sanitize_market_attributes(resolved_category_name, item.attributes)
        return item

    def create(self, item: Market) -> Market:
        item = self._sanitize_market_item(item)
        if item.url:
            existing = self.repository.find_by_url(item.url)
            if existing:
                raise DuplicateEntityException("Market", "url", item.url)
        return self.repository.save(item)

    def get_by_id(self, item_id: int) -> Market:
        item = self.repository.find_by_id(item_id)
        if not item:
            raise EntityNotFoundException("Market", item_id)
        return item

    def get_by_ids(self, item_ids: list[int]) -> list[Market]:
        normalized_ids = [int(item_id) for item_id in item_ids if int(item_id) > 0]
        if not normalized_ids:
            return []
        return self.repository.find_by_ids(normalized_ids)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Market]:
        return self.repository.find_all(limit=limit, offset=offset)

    def update(self, item: Market) -> Market:
        existing = self.repository.find_by_id(item.id)
        if not existing:
            raise EntityNotFoundException("Market", item.id or 0)

        item = self._sanitize_market_item(item)
        item.version = (existing.version or 0) + 1
        return self.repository.update(item)

    def patch(
        self,
        *,
        item_id: int,
        updates: dict[str, Any],
        expected_version: Optional[int] = None,
        submitted_at: Optional[datetime] = None,
    ) -> Market:
        existing = self.repository.find_by_id(item_id)
        if not existing:
            raise EntityNotFoundException("Market", item_id)

        if expected_version is not None and (existing.version or 0) != expected_version:
            raise ConcurrencyConflictException(
                f"Conflito de concorrencia no item {item_id}: versao atual={existing.version}, versao esperada={expected_version}"
            )

        if submitted_at and existing.updated_at:
            submitted_at_aware = submitted_at.replace(tzinfo=timezone.utc) if submitted_at.tzinfo is None else submitted_at.astimezone(timezone.utc)
            updated_at_aware = existing.updated_at.replace(tzinfo=timezone.utc) if existing.updated_at.tzinfo is None else existing.updated_at.astimezone(timezone.utc)
            if updated_at_aware > submitted_at_aware:
                raise ConcurrencyConflictException(
                    f"Conflito temporal no item {item_id}: updated_at={updated_at_aware.isoformat()} > submitted_at={submitted_at_aware.isoformat()}"
                )

        valid_updates: dict[str, Any] = {}
        for field, value in updates.items():
            if field in self.PATCHABLE_FIELDS:
                if field == "description":
                    value = self._normalize_description_text(value)
                valid_updates[field] = value

        if "attributes" in valid_updates:
            target_category_id = valid_updates.get("category_id", existing.category_id)
            valid_updates["attributes"] = self._sanitize_market_attributes(
                self._resolve_category_name(target_category_id),
                valid_updates["attributes"],
            )

        if not valid_updates:
            raise InvalidEntityException("Nenhum campo valido foi informado para patch")

        for field, value in valid_updates.items():
            setattr(existing, field, value)

        existing.version = (existing.version or 0) + 1
        return self.repository.update(existing)

    def delete(self, item_id: int) -> None:
        existing = self.repository.find_by_id(item_id)
        if not existing:
            raise EntityNotFoundException("Market", item_id)
        self.repository.delete(item_id)

    def delete_many(self, item_ids: list[int]) -> int:
        normalized_ids = sorted({int(item_id) for item_id in item_ids if int(item_id) > 0})
        if not normalized_ids:
            raise InvalidEntityException("Nenhum item valido foi informado para exclusao em lote")

        existing_ids = sorted(set(self.repository.find_existing_ids(normalized_ids)))
        if not existing_ids:
            return 0
        return self.repository.delete_many(existing_ids)

    def ingest_raw(self, raw_data: dict) -> Market:
        source_id = None
        category_id = None
        category_name = None

        source_data = raw_data.get("source", {})
        if source_data and self.source_service:
            source_name = source_data.get("name", "unknown")
            source = self.source_service.find_or_create_by_name(source_name)
            source_id = source.id

            if self.category_service:
                category_name = raw_data.get("category", {}).get("name", "EMPREGOS")
                category = self.category_service.find_or_create_primary_for_source(source.id or 0, category_name)
                category_id = category.id

        scraped = raw_data.get("scraped_data", {})
        item = self._sanitize_market_item(
            Market(
                url=raw_data.get("url", ""),
                source_id=source_id,
                category_id=category_id,
                title=scraped.get("title"),
                description=scraped.get("description"),
                price=scraped.get("price"),
                currency=scraped.get("currency", "BRL"),
                location=scraped.get("location", {}),
                state=scraped.get("state"),
                city=scraped.get("city"),
                zip_code=scraped.get("zip_code"),
                street=scraped.get("street"),
                contact_name=scraped.get("contact_name"),
                contact_phone=scraped.get("contact_phone"),
                contact_email=scraped.get("contact_email"),
                images=scraped.get("images", []),
                videos=scraped.get("videos", []),
                documents=scraped.get("documents", []),
                links=scraped.get("links", []),
                attributes=scraped.get("attributes", {}),
                version=raw_data.get("version", 1),
            ),
            category_name=category_name,
        )

        dedupe_key = None
        if isinstance(item.attributes, dict):
            raw_dedupe_key = item.attributes.get("dedupe_key")
            if isinstance(raw_dedupe_key, str) and raw_dedupe_key.strip():
                dedupe_key = raw_dedupe_key.strip()

        external_links = [
            self._normalize_market_link(link)
            for link in (item.links or [])
            if isinstance(link, str) and link.strip() and "t.me/" not in link and not link.startswith("telegram://")
        ]

        existing = None
        if item.url:
            existing = self.repository.find_by_url(item.url)
        if existing is None and source_id and external_links:
            existing = self.repository.find_by_source_and_any_link(source_id, external_links)
        if existing is None and source_id and dedupe_key:
            existing = self.repository.find_by_source_and_attribute(source_id, "dedupe_key", dedupe_key)

        if existing:
            existing.source_id = item.source_id
            existing.category_id = item.category_id
            existing.url = existing.url or item.url
            existing.title = item.title or existing.title
            existing.description = item.description or existing.description
            existing.price = item.price or existing.price
            existing.currency = item.currency
            existing.location = item.location or existing.location
            existing.state = item.state or existing.state
            existing.city = item.city or existing.city
            existing.zip_code = item.zip_code or existing.zip_code
            existing.street = item.street or existing.street
            existing.contact_name = item.contact_name or existing.contact_name
            existing.contact_phone = item.contact_phone or existing.contact_phone
            existing.contact_email = item.contact_email or existing.contact_email
            existing.images = item.images or existing.images
            existing.videos = item.videos or existing.videos
            existing.documents = item.documents or existing.documents
            existing.links = list(dict.fromkeys([*(existing.links or []), *(item.links or [])]))
            existing.attributes = self._sanitize_market_attributes(
                category_name,
                {**(existing.attributes or {}), **(item.attributes or {})},
            )
            existing.version = (existing.version or 0) + 1
            updated = self.repository.update(existing)
            logger.info("Market updated: %s (id=%s)", updated.url, updated.id)
            return updated

        saved = self.repository.save(item)
        logger.info("Market created: %s (id=%s)", saved.url, saved.id)
        return saved

    def search_items(self, query: str, size: int = 20) -> list[Market]:
        return self.repository.find_with_filters(text_query=query, limit=size, offset=0)

    def find_with_filters(
        self,
        text_query: Optional[str] = None,
        category: Optional[str] = None,
        categories: Optional[list[str]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        source: Optional[str] = None,
        created_since: Optional[datetime] = None,
        contract_type: Optional[str] = None,
        seniority: Optional[str] = None,
        has_contact: Optional[bool] = None,
        has_salary_range: Optional[bool] = None,
        software_focus: Optional[bool] = None,
        actionable_now: Optional[bool] = None,
        exclude_disabled_categories: bool = False,
        order_by: str = "created_at",
        order_direction: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        return self.repository.find_with_filters(
            text_query=text_query,
            category=category,
            categories=categories,
            min_price=min_price,
            max_price=max_price,
            currency=currency,
            state=state,
            city=city,
            source=source,
            created_since=created_since,
            contract_type=contract_type,
            seniority=seniority,
            has_contact=has_contact,
            has_salary_range=has_salary_range,
            software_focus=software_focus,
            actionable_now=actionable_now,
            exclude_disabled_categories=exclude_disabled_categories,
            order_by=order_by,
            order_direction=order_direction,
            limit=limit,
            offset=offset,
        )

    def count_with_filters(
        self,
        text_query: Optional[str] = None,
        category: Optional[str] = None,
        categories: Optional[list[str]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        currency: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        source: Optional[str] = None,
        created_since: Optional[datetime] = None,
        contract_type: Optional[str] = None,
        seniority: Optional[str] = None,
        has_contact: Optional[bool] = None,
        has_salary_range: Optional[bool] = None,
        software_focus: Optional[bool] = None,
        actionable_now: Optional[bool] = None,
        exclude_disabled_categories: bool = False,
    ) -> int:
        return self.repository.count_with_filters(
            text_query=text_query,
            category=category,
            categories=categories,
            min_price=min_price,
            max_price=max_price,
            currency=currency,
            state=state,
            city=city,
            source=source,
            created_since=created_since,
            contract_type=contract_type,
            seniority=seniority,
            has_contact=has_contact,
            has_salary_range=has_salary_range,
            software_focus=software_focus,
            actionable_now=actionable_now,
            exclude_disabled_categories=exclude_disabled_categories,
        )

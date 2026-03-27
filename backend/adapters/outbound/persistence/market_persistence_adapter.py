"""SQLite-oriented market repository for kids-jobs."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Optional

from sqlalchemy.orm import Session

from adapters.outbound.persistence.models.market_model import MarketModel
from adapters.outbound.persistence.models.source_model import SourceModel
from application.domain.entities.market import Market
from application.ports.outbound.persistence.market_persistence_port import MarketPersistencePort


class MarketPersistenceAdapter(MarketPersistencePort):
    def __init__(self, session: Session):
        self.session = session

    def save(self, item: Market) -> Market:
        model = MarketModel.from_entity(item)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def find_by_id(self, item_id: int) -> Optional[Market]:
        model = self.session.query(MarketModel).filter_by(id=item_id).first()
        return model.to_entity() if model else None

    def find_by_ids(self, item_ids: list[int]) -> list[Market]:
        normalized_ids = [int(item_id) for item_id in item_ids if int(item_id) > 0]
        if not normalized_ids:
            return []
        models = self.session.query(MarketModel).filter(MarketModel.id.in_(normalized_ids)).all()
        model_by_id = {int(model.id): model for model in models}
        return [model_by_id[item_id].to_entity() for item_id in normalized_ids if item_id in model_by_id]

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Market]:
        models = self.session.query(MarketModel).order_by(MarketModel.created_at.desc()).offset(offset).limit(limit).all()
        return [model.to_entity() for model in models]

    def update(self, item: Market) -> Market:
        model = self.session.query(MarketModel).filter_by(id=item.id).first()
        if model is None:
            raise ValueError(f"Market {item.id} not found")

        model.source_id = item.source_id
        model.url = item.url
        model.title = item.title
        model.description = item.description
        model.price = item.price
        model.currency = item.currency
        model.location = item.location or {}
        model.state = item.state
        model.city = item.city
        model.zip_code = item.zip_code
        model.street = item.street
        model.contact_name = item.contact_name
        model.contact_phone = item.contact_phone
        model.contact_email = item.contact_email
        model.images = list(item.images or [])
        model.videos = list(item.videos or [])
        model.documents = list(item.documents or [])
        model.links = list(item.links or [])
        model.attributes = item.attributes or {}
        model.version = item.version
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def delete(self, item_id: int) -> None:
        model = self.session.query(MarketModel).filter_by(id=item_id).first()
        if model:
            self.session.delete(model)
            self.session.commit()

    def delete_many(self, item_ids: list[int]) -> int:
        if not item_ids:
            return 0
        deleted_count = self.session.query(MarketModel).filter(MarketModel.id.in_(item_ids)).delete(synchronize_session=False)
        self.session.commit()
        return int(deleted_count or 0)

    def find_existing_ids(self, item_ids: list[int]) -> list[int]:
        if not item_ids:
            return []
        rows = self.session.query(MarketModel.id).filter(MarketModel.id.in_(item_ids)).all()
        return [int(row[0]) for row in rows]

    def find_by_url(self, url: str) -> Optional[Market]:
        model = self.session.query(MarketModel).filter_by(url=url).first()
        return model.to_entity() if model else None

    def find_by_source_and_any_link(self, source_id: int, links: list[str]) -> Optional[Market]:
        normalized_links = {str(link).strip() for link in links if str(link).strip()}
        if not normalized_links:
            return None

        models = self.session.query(MarketModel).filter(MarketModel.source_id == source_id).order_by(MarketModel.updated_at.desc()).all()
        for model in models:
            if normalized_links.intersection({str(link).strip() for link in (model.links or []) if str(link).strip()}):
                return model.to_entity()
        return None

    def find_by_source_and_attribute(self, source_id: int, attribute_key: str, attribute_value: str) -> Optional[Market]:
        if not attribute_key or not attribute_value:
            return None
        models = self.session.query(MarketModel).filter(MarketModel.source_id == source_id).order_by(MarketModel.updated_at.desc()).all()
        for model in models:
            attributes = model.attributes or {}
            if isinstance(attributes, dict) and str(attributes.get(attribute_key) or "").strip() == attribute_value:
                return model.to_entity()
        return None

    def count(self) -> int:
        return self.session.query(MarketModel).count()

    def _source_name_map(self) -> dict[int, str]:
        return {int(model.id): model.name for model in self.session.query(SourceModel).all()}

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return " ".join((value or "").strip().lower().split())

    @staticmethod
    def _has_valid_contact(item: Market) -> bool:
        digits = re.sub(r"[^0-9]", "", item.contact_phone or "")
        has_phone = len(digits) >= 8
        has_email = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (item.contact_email or "").strip(), re.IGNORECASE))
        return has_phone or has_email

    @staticmethod
    def _has_salary_range(item: Market) -> bool:
        attributes = item.attributes or {}
        value = attributes.get("salary_range") if isinstance(attributes, dict) else None
        return isinstance(value, (int, float)) and float(value) > 0

    def _filter_entities(
        self,
        *,
        text_query: Optional[str] = None,
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
    ) -> list[Market]:
        items = [model.to_entity() for model in self.session.query(MarketModel).all()]
        source_map = self._source_name_map()
        normalized_source = self._normalize_text(source)
        normalized_currency = self._normalize_text(currency)
        normalized_state = self._normalize_text(state).upper() if state else ""
        normalized_city = self._normalize_text(city)
        normalized_query = self._normalize_text(text_query)
        normalized_contract_type = self._normalize_text(contract_type)
        normalized_seniority = self._normalize_text(seniority)

        filtered: list[Market] = []
        for item in items:
            source_name = (source_map.get(int(item.source_id or 0)) or "").strip().lower()
            attributes = item.attributes if isinstance(item.attributes, dict) else {}

            if normalized_source and source_name != normalized_source:
                continue
            if normalized_query:
                haystack = " ".join(
                    [
                        item.title or "",
                        item.description or "",
                        source_name,
                        str(attributes.get("company") or ""),
                    ]
                ).lower()
                if normalized_query not in haystack:
                    continue
            if min_price is not None and (item.price is None or item.price < min_price):
                continue
            if max_price is not None:
                if float(max_price) == 0:
                    if item.price is not None:
                        continue
                elif item.price is None or item.price > max_price:
                    continue
            if normalized_currency:
                current_currency = self._normalize_text(item.currency)
                if normalized_currency == "other":
                    if current_currency in {"", "brl", "usd"}:
                        continue
                elif current_currency != normalized_currency:
                    continue
            if normalized_state and self._normalize_text(item.state).upper() != normalized_state:
                continue
            if normalized_city and normalized_city not in self._normalize_text(item.city):
                continue
            if created_since is not None and item.created_at and item.created_at < created_since:
                continue
            if normalized_contract_type:
                current_contract_type = self._normalize_text(str(attributes.get("contract_type") or ""))
                if normalized_contract_type == "pj" and current_contract_type not in {"pj", "pessoa juridica", "pessoa jurídica"}:
                    continue
                if normalized_contract_type == "clt" and current_contract_type != "clt":
                    continue
            if normalized_seniority:
                current_seniority = self._normalize_text(str(attributes.get("seniority") or ""))
                variants = {
                    "junior": {"junior", "júnior", "jr"},
                    "pleno": {"pleno"},
                    "senior": {"senior", "sênior", "sr"},
                }.get(normalized_seniority, {normalized_seniority})
                if current_seniority not in variants:
                    continue
            if has_contact is True and not self._has_valid_contact(item):
                continue
            if has_contact is False and self._has_valid_contact(item):
                continue
            if has_salary_range is True and not self._has_salary_range(item):
                continue
            if has_salary_range is False and self._has_salary_range(item):
                continue
            if software_focus is not None:
                current_value = self._normalize_text(str(attributes.get("software_focus") or ""))
                truthy = current_value in {"true", "1", "sim"}
                if software_focus != truthy:
                    continue
            if actionable_now is not None:
                current_value = self._normalize_text(str(attributes.get("actionable_now") or ""))
                truthy = current_value in {"true", "1", "sim"}
                if actionable_now != truthy:
                    continue

            filtered.append(item)

        return filtered

    def count_with_filters(
        self,
        text_query: Optional[str] = None,
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
    ) -> int:
        return len(
            self._filter_entities(
                text_query=text_query,
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
            )
        )

    def find_with_filters(
        self,
        text_query: Optional[str] = None,
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
        order_by: str = "created_at",
        order_direction: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        items = self._filter_entities(
            text_query=text_query,
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
        )

        reverse = order_direction.lower() != "asc"
        if order_by == "updated_at":
            items.sort(key=lambda item: item.updated_at or datetime.min, reverse=reverse)
        elif order_by == "price":
            items.sort(key=lambda item: (item.price is None, item.price or 0), reverse=reverse)
        elif order_by == "title":
            items.sort(key=lambda item: (item.title or "").lower(), reverse=reverse)
        else:
            items.sort(key=lambda item: item.created_at or datetime.min, reverse=reverse)

        return items[offset: offset + limit]

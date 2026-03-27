"""
Source Persistence Adapter - SQLite Implementation
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from application.domain.entities.source import Source
from application.ports.outbound.persistence.source_persistence_port import SourcePersistencePort
from adapters.outbound.persistence.models.source_model import SourceModel


class SourcePersistenceAdapter(SourcePersistencePort):

    def __init__(self, session: Session):
        self.session = session

    def save(self, source: Source) -> Source:
        model = SourceModel.from_entity(source)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def find_by_id(self, source_id: int) -> Optional[Source]:
        model = self.session.query(SourceModel).filter_by(id=source_id).first()
        return model.to_entity() if model else None

    def find_by_name(self, name: str) -> Optional[Source]:
        normalized_name = (name or "").strip().lower()
        model = (
            self.session.query(SourceModel)
            .filter(func.lower(SourceModel.name) == normalized_name)
            .first()
        )
        return model.to_entity() if model else None

    def find_all(self, enabled_only: bool = False) -> list[Source]:
        query = self.session.query(SourceModel)
        if enabled_only:
            query = query.filter_by(enabled=True)
        return [m.to_entity() for m in query.order_by(SourceModel.id).all()]

    def update(self, source: Source) -> Source:
        model = self.session.query(SourceModel).filter_by(id=source.id).first()
        if model:
            model.name = source.name
            model.enabled = source.enabled
            model.scraper_base_url = source.scraper_base_url
            model.scraper_type = source.scraper_type
            model.scraper_schedule = source.scraper_schedule
            model.extra_config = SourceModel.from_entity(source).extra_config
            model.description = source.description
            model.last_extraction_status = source.last_extraction_status
            model.last_extraction_http_status = source.last_extraction_http_status
            model.last_extraction_message = source.last_extraction_message
            model.last_extraction_at = source.last_extraction_at
            self.session.commit()
            self.session.refresh(model)
            return model.to_entity()
        raise ValueError(f"Source {source.id} not found")

    def delete(self, source_id: int) -> None:
        self.session.query(SourceModel).filter_by(id=source_id).delete()
        self.session.commit()

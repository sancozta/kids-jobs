"""
Source Service - Domain Service
"""
import logging
from typing import Optional

from application.domain.entities.source import Source
from application.ports.outbound.persistence.source_persistence_port import SourcePersistencePort

logger = logging.getLogger(__name__)


class SourceService:

    def __init__(self, persistence: SourcePersistencePort):
        self.persistence = persistence

    def create(self, source: Source) -> Source:
        existing = self.persistence.find_by_name(source.name)
        if existing:
            raise ValueError(f"Source '{source.name}' already exists")
        result = self.persistence.save(source)
        logger.info(f"Source created: {result.name} (id={result.id})")
        return result

    def get_by_id(self, source_id: int) -> Optional[Source]:
        return self.persistence.find_by_id(source_id)

    def get_by_name(self, source_name: str) -> Optional[Source]:
        return self.persistence.find_by_name(source_name)

    def find_or_create_by_name(self, source_name: str) -> Source:
        normalized_name = (source_name or "").strip().lower() or "unknown"
        existing = self.persistence.find_by_name(normalized_name)
        if existing:
            return existing
        return self.create(Source(name=normalized_name))

    def get_all(self, enabled_only: bool = False) -> list[Source]:
        return self.persistence.find_all(enabled_only=enabled_only)

    def update(self, source: Source) -> Source:
        existing = self.persistence.find_by_id(source.id)
        if not existing:
            raise ValueError(f"Source {source.id} not found")
        result = self.persistence.update(source)
        logger.info(f"Source updated: {result.name} (id={result.id})")
        return result

    def toggle(self, source_id: int) -> Source:
        existing = self.persistence.find_by_id(source_id)
        if not existing:
            raise ValueError(f"Source {source_id} not found")
        existing.enabled = not existing.enabled
        result = self.persistence.update(existing)
        logger.info(f"Source toggled: {result.name} enabled={result.enabled}")
        return result

    def delete(self, source_id: int) -> None:
        existing = self.persistence.find_by_id(source_id)
        if not existing:
            raise ValueError(f"Source {source_id} not found")
        self.persistence.delete(source_id)
        logger.info(f"Source deleted: {existing.name} (id={source_id})")

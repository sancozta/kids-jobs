"""
Category Service - Domain Service
"""
import logging
from typing import Optional

from application.domain.entities.category import Category
from application.ports.outbound.persistence.category_persistence_port import CategoryPersistencePort

logger = logging.getLogger(__name__)


class CategoryService:

    def __init__(self, persistence: CategoryPersistencePort):
        self.persistence = persistence

    def create(self, category: Category) -> Category:
        result = self.persistence.save(category)
        logger.info(f"Category created: {result.name} (id={result.id}, source_id={result.source_id})")
        return result

    def get_by_id(self, category_id: int) -> Optional[Category]:
        return self.persistence.find_by_id(category_id)

    def get_by_source_id(self, source_id: int, enabled_only: bool = False) -> list[Category]:
        return self.persistence.find_by_source_id(source_id, enabled_only=enabled_only)

    def get_all(self) -> list[Category]:
        return self.persistence.find_all()

    def find_primary_by_source_id(self, source_id: int) -> Optional[Category]:
        categories = self.get_by_source_id(source_id, enabled_only=False)
        return categories[0] if categories else None

    def find_or_create_primary_for_source(self, source_id: int, name: str) -> Category:
        existing = self.find_primary_by_source_id(source_id)
        normalized_name = (name or "").strip().upper() or "EMPREGOS"
        if existing:
            if existing.name != normalized_name or not existing.enabled:
                existing.name = normalized_name
                existing.enabled = True
                return self.update(existing)
            return existing

        return self.create(
            Category(
                name=normalized_name,
                source_id=source_id,
                enabled=True,
            )
        )

    def update(self, category: Category) -> Category:
        existing = self.persistence.find_by_id(category.id)
        if not existing:
            raise ValueError(f"Category {category.id} not found")
        result = self.persistence.update(category)
        logger.info(f"Category updated: {result.name} (id={result.id})")
        return result

    def delete(self, category_id: int) -> None:
        existing = self.persistence.find_by_id(category_id)
        if not existing:
            raise ValueError(f"Category {category_id} not found")
        self.persistence.delete(category_id)
        logger.info(f"Category deleted: {existing.name} (id={category_id})")

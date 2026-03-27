"""
Category Model - SQLAlchemy Model for SQLite
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey

from configuration.database_configuration import Base
from application.domain.entities.category import Category


class CategoryModel(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    scrape_path = Column(String, nullable=True)
    schedule = Column(String, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_entity(self) -> Category:
        return Category(
            id=self.id,
            name=self.name,
            source_id=self.source_id,
            category_id=self.category_id,
            scrape_path=self.scrape_path,
            schedule=self.schedule,
            enabled=self.enabled,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: Category) -> "CategoryModel":
        return CategoryModel(
            id=entity.id,
            name=entity.name,
            source_id=entity.source_id,
            category_id=entity.category_id,
            scrape_path=entity.scrape_path,
            schedule=entity.schedule,
            enabled=entity.enabled,
        )

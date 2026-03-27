"""
Category Persistence Adapter - SQLite Implementation
"""
from typing import Optional

from sqlalchemy.orm import Session

from application.domain.entities.category import Category
from application.ports.outbound.persistence.category_persistence_port import CategoryPersistencePort
from adapters.outbound.persistence.models.category_model import CategoryModel


class CategoryPersistenceAdapter(CategoryPersistencePort):

    def __init__(self, session: Session):
        self.session = session

    def save(self, category: Category) -> Category:
        model = CategoryModel.from_entity(category)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def find_by_id(self, category_id: int) -> Optional[Category]:
        model = self.session.query(CategoryModel).filter_by(id=category_id).first()
        return model.to_entity() if model else None

    def find_by_source_id(self, source_id: int, enabled_only: bool = False) -> list[Category]:
        query = self.session.query(CategoryModel).filter_by(source_id=source_id)
        if enabled_only:
            query = query.filter_by(enabled=True)
        return [m.to_entity() for m in query.order_by(CategoryModel.id).all()]

    def find_all(self) -> list[Category]:
        return [m.to_entity() for m in self.session.query(CategoryModel).order_by(CategoryModel.id).all()]

    def update(self, category: Category) -> Category:
        model = self.session.query(CategoryModel).filter_by(id=category.id).first()
        if model:
            model.name = category.name
            model.source_id = category.source_id
            model.category_id = category.category_id
            model.scrape_path = category.scrape_path
            model.schedule = category.schedule
            model.enabled = category.enabled
            self.session.commit()
            self.session.refresh(model)
            return model.to_entity()
        raise ValueError(f"Category {category.id} not found")

    def delete(self, category_id: int) -> None:
        self.session.query(CategoryModel).filter_by(id=category_id).delete()
        self.session.commit()

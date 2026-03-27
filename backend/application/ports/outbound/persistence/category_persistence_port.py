"""
Category Persistence Port - Outbound Port
"""
from abc import ABC, abstractmethod
from typing import Optional

from application.domain.entities.category import Category


class CategoryPersistencePort(ABC):

    @abstractmethod
    def save(self, category: Category) -> Category:
        ...

    @abstractmethod
    def find_by_id(self, category_id: int) -> Optional[Category]:
        ...

    @abstractmethod
    def find_by_source_id(self, source_id: int, enabled_only: bool = False) -> list[Category]:
        ...

    @abstractmethod
    def find_all(self) -> list[Category]:
        ...

    @abstractmethod
    def update(self, category: Category) -> Category:
        ...

    @abstractmethod
    def delete(self, category_id: int) -> None:
        ...

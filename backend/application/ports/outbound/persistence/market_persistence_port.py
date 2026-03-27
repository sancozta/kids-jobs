"""
Market Repository Port - Outbound Port
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from application.domain.entities.market import Market


class MarketPersistencePort(ABC):

    @abstractmethod
    def save(self, item: Market) -> Market: ...

    @abstractmethod
    def find_by_id(self, item_id: int) -> Optional[Market]: ...

    @abstractmethod
    def find_by_ids(self, item_ids: list[int]) -> list[Market]: ...

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> list[Market]: ...

    @abstractmethod
    def update(self, item: Market) -> Market: ...

    @abstractmethod
    def delete(self, item_id: int) -> None: ...

    @abstractmethod
    def delete_many(self, item_ids: list[int]) -> int: ...

    @abstractmethod
    def find_existing_ids(self, item_ids: list[int]) -> list[int]: ...

    @abstractmethod
    def find_by_url(self, url: str) -> Optional[Market]: ...

    @abstractmethod
    def find_by_source_and_any_link(self, source_id: int, links: list[str]) -> Optional[Market]: ...

    @abstractmethod
    def find_by_source_and_attribute(self, source_id: int, attribute_key: str, attribute_value: str) -> Optional[Market]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
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
    ) -> int: ...

    @abstractmethod
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
        offset: int = 0
    ) -> list[Market]: ...

"""
Source Persistence Port - Outbound Port
"""
from abc import ABC, abstractmethod
from typing import Optional

from application.domain.entities.source import Source


class SourcePersistencePort(ABC):

    @abstractmethod
    def save(self, source: Source) -> Source:
        ...

    @abstractmethod
    def find_by_id(self, source_id: int) -> Optional[Source]:
        ...

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Source]:
        ...

    @abstractmethod
    def find_all(self, enabled_only: bool = False) -> list[Source]:
        ...

    @abstractmethod
    def update(self, source: Source) -> Source:
        ...

    @abstractmethod
    def delete(self, source_id: int) -> None:
        ...

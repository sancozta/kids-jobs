"""Outbound persistence port for resume documents."""
from abc import ABC, abstractmethod
from typing import Optional

from application.domain.entities.resume_document import ResumeDocument


class ResumeDocumentPersistencePort(ABC):
    @abstractmethod
    def find_by_key(self, key: str) -> Optional[ResumeDocument]: ...

    @abstractmethod
    def save(self, document: ResumeDocument) -> ResumeDocument: ...

    @abstractmethod
    def update(self, document: ResumeDocument) -> ResumeDocument: ...

"""Domain service for resume document persistence."""
from application.domain.entities.resume_document import ResumeDocument
from application.ports.outbound.persistence.resume_document_persistence_port import ResumeDocumentPersistencePort


class ResumeDocumentService:
    DEFAULT_KEY = "default"
    DEFAULT_LOCALE = "pt"

    def __init__(self, repository: ResumeDocumentPersistencePort):
        self.repository = repository

    @classmethod
    def _build_key(cls, locale: str) -> str:
        return f"{cls.DEFAULT_KEY}:{locale}"

    def get_default(self, locale: str = DEFAULT_LOCALE) -> ResumeDocument | None:
        key = self._build_key(locale)
        document = self.repository.find_by_key(key)
        if document is not None:
            return document
        if locale == self.DEFAULT_LOCALE:
            return self.repository.find_by_key(self.DEFAULT_KEY)
        return None

    def save_default(self, payload: dict, locale: str = DEFAULT_LOCALE) -> ResumeDocument:
        key = self._build_key(locale)
        existing = self.repository.find_by_key(key)
        if existing:
            existing.payload = payload
            return self.repository.update(existing)
        return self.repository.save(ResumeDocument(key=key, payload=payload))

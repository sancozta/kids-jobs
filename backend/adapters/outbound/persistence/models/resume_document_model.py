"""Resume document model for SQLite."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint

from application.domain.entities.resume_document import ResumeDocument
from configuration.database_configuration import Base


class ResumeDocumentModel(Base):
    __tablename__ = "resume_documents"
    __table_args__ = (UniqueConstraint("key", name="uq_resume_documents_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_entity(self) -> ResumeDocument:
        return ResumeDocument(
            id=self.id,
            key=self.key,
            payload=self.payload or {},
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: ResumeDocument) -> "ResumeDocumentModel":
        return ResumeDocumentModel(
            id=entity.id,
            key=entity.key,
            payload=entity.payload,
        )

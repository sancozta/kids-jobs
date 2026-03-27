"""PostgreSQL persistence adapter for resume documents."""
from sqlalchemy.orm import Session

from adapters.outbound.persistence.models.resume_document_model import ResumeDocumentModel
from application.domain.entities.resume_document import ResumeDocument
from application.ports.outbound.persistence.resume_document_persistence_port import ResumeDocumentPersistencePort


class ResumeDocumentPersistenceAdapter(ResumeDocumentPersistencePort):
    def __init__(self, session: Session):
        self.session = session

    def find_by_key(self, key: str) -> ResumeDocument | None:
        model = self.session.query(ResumeDocumentModel).filter_by(key=key).first()
        return model.to_entity() if model else None

    def save(self, document: ResumeDocument) -> ResumeDocument:
        model = ResumeDocumentModel.from_entity(document)
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return model.to_entity()

    def update(self, document: ResumeDocument) -> ResumeDocument:
        model = self.session.query(ResumeDocumentModel).filter_by(key=document.key).first()
        if model is None:
            return self.save(document)
        model.payload = document.payload
        self.session.flush()
        self.session.refresh(model)
        return model.to_entity()

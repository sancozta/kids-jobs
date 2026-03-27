"""Dependency helpers for kids-jobs backend."""
from fastapi import Depends
from sqlalchemy.orm import Session

from adapters.outbound.persistence.market_persistence_adapter import MarketPersistenceAdapter
from adapters.outbound.persistence.resume_document_persistence_adapter import ResumeDocumentPersistenceAdapter
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from application.domain.services.market_service import MarketService
from application.domain.services.resume_document_service import ResumeDocumentService
from application.domain.services.source_service import SourceService
from configuration.database_configuration import get_db


def get_source_service(db: Session = Depends(get_db)) -> SourceService:
    return SourceService(persistence=SourcePersistenceAdapter(session=db))


def get_market_service(db: Session = Depends(get_db)) -> MarketService:
    return MarketService(
        repository=MarketPersistenceAdapter(session=db),
        source_service=SourceService(persistence=SourcePersistenceAdapter(session=db)),
    )


def get_resume_document_service(db: Session = Depends(get_db)) -> ResumeDocumentService:
    return ResumeDocumentService(repository=ResumeDocumentPersistenceAdapter(session=db))

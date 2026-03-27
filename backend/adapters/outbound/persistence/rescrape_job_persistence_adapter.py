"""
Rescrape Job Persistence Adapter - SQLite implementation
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from adapters.outbound.persistence.models.rescrape_job_model import RescrapeJobModel
from application.domain.entities.rescrape_job import RescrapeJob
from application.ports.outbound.persistence.rescrape_job_persistence_port import RescrapeJobPersistencePort


class RescrapeJobPersistenceAdapter(RescrapeJobPersistencePort):

    def __init__(self, session: Session):
        self.session = session

    def save(self, job: RescrapeJob) -> RescrapeJob:
        model = RescrapeJobModel.from_entity(job)
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def update(self, job: RescrapeJob) -> RescrapeJob:
        model = self.session.query(RescrapeJobModel).filter_by(id=job.id).first()
        if not model:
            raise ValueError(f"Rescrape job {job.id} not found")

        model.source_name = job.source_name
        model.url = job.url
        model.status = job.status
        model.market_item_id = job.market_item_id
        model.attempts = job.attempts
        model.last_error = job.last_error
        model.last_processed_at = job.last_processed_at

        self.session.commit()
        self.session.refresh(model)
        return model.to_entity()

    def find_by_id(self, job_id: int) -> Optional[RescrapeJob]:
        model = self.session.query(RescrapeJobModel).filter_by(id=job_id).first()
        return model.to_entity() if model else None

    def find_active_by_source_url(self, source_name: str, url: str) -> Optional[RescrapeJob]:
        normalized_source_name = (source_name or "").strip().lower()
        normalized_url = (url or "").strip()
        if not normalized_source_name or not normalized_url:
            return None

        model = (
            self.session.query(RescrapeJobModel)
            .filter(func.lower(RescrapeJobModel.source_name) == normalized_source_name)
            .filter(RescrapeJobModel.url == normalized_url)
            .filter(RescrapeJobModel.status.in_(("queued", "processing")))
            .order_by(RescrapeJobModel.id.desc())
            .first()
        )
        return model.to_entity() if model else None

    def find_pending(self, limit: int = 10) -> list[RescrapeJob]:
        models = (
            self.session.query(RescrapeJobModel)
            .filter_by(status="queued")
            .order_by(RescrapeJobModel.created_at.asc(), RescrapeJobModel.id.asc())
            .limit(limit)
            .all()
        )
        return [model.to_entity() for model in models]

    def find_all(self, *, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[RescrapeJob]:
        query = self.session.query(RescrapeJobModel)
        if status:
            query = query.filter_by(status=status)
        models = (
            query.order_by(RescrapeJobModel.created_at.desc(), RescrapeJobModel.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [model.to_entity() for model in models]

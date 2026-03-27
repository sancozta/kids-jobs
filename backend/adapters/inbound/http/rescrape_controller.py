"""
Rescrape Queue Controller
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from adapters.outbound.persistence.rescrape_job_persistence_adapter import RescrapeJobPersistenceAdapter
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from application.domain.services.rescrape_job_service import (
    RescrapeEnqueueItem,
    RescrapeJobService,
)
from application.domain.services.source_service import SourceService
from configuration.database_configuration import get_db
from configuration.settings_configuration import settings

router = APIRouter(prefix="/api/v1/rescrape-jobs", tags=["Rescrape Queue"])


class RescrapeJobItemSchema(BaseModel):
    source_name: str = Field(..., description="Nome da fonte/scraper")
    url: str = Field(..., description="URL canônica do item")
    market_item_id: Optional[int] = Field(None, description="ID atual no market, quando houver")


class RescrapeJobCreateSchema(BaseModel):
    items: list[RescrapeJobItemSchema] = Field(default_factory=list)


class RescrapeJobResponseSchema(BaseModel):
    id: int
    source_name: str
    url: str
    status: Literal["queued", "processing", "completed", "error"]
    market_item_id: Optional[int] = None
    attempts: int
    last_error: Optional[str] = None
    last_processed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RescrapeJobCreateResponseSchema(BaseModel):
    queued_count: int
    deduplicated_count: int
    jobs: list[RescrapeJobResponseSchema]


class RescrapeJobProcessResponseSchema(BaseModel):
    processed_count: int
    completed_count: int
    error_count: int
    jobs: list[RescrapeJobResponseSchema]


def _get_service(db: Session = Depends(get_db)) -> RescrapeJobService:
    persistence = RescrapeJobPersistenceAdapter(session=db)
    source_service = SourceService(persistence=SourcePersistenceAdapter(session=db))
    return RescrapeJobService(
        persistence=persistence,
        source_service=source_service,
    )


@router.post("", response_model=RescrapeJobCreateResponseSchema, status_code=201)
def create_rescrape_jobs(
    body: RescrapeJobCreateSchema,
    request: Request,
    service: RescrapeJobService = Depends(_get_service),
):
    publish_fn = getattr(request.app.state, "publish_rescrape_job", None)
    if callable(publish_fn):
        service.publish_callable = publish_fn

    enqueue_items = [
        RescrapeEnqueueItem(
            source_name=item.source_name,
            url=item.url,
            market_item_id=item.market_item_id,
        )
        for item in body.items
    ]
    result = service.enqueue_many(enqueue_items)
    if not result.jobs:
        raise HTTPException(status_code=400, detail="Nenhum item válido foi enviado para reprocessamento")

    return RescrapeJobCreateResponseSchema(
        queued_count=result.queued_count,
        deduplicated_count=result.deduplicated_count,
        jobs=[RescrapeJobResponseSchema.model_validate(job.__dict__) for job in result.jobs],
    )


@router.get("", response_model=list[RescrapeJobResponseSchema])
def list_rescrape_jobs(
    status: Optional[str] = Query(None, description="Filtro por status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: RescrapeJobService = Depends(_get_service),
):
    jobs = service.list_jobs(status=status, limit=limit, offset=offset)
    return [RescrapeJobResponseSchema.model_validate(job.__dict__) for job in jobs]


@router.post("/process", response_model=RescrapeJobProcessResponseSchema)
def process_rescrape_jobs(
    request: Request,
    limit: int = Query(settings.rescrape_queue_batch_size, ge=1, le=100),
):
    process_pending_fn = getattr(request.app.state, "process_pending_rescrape_jobs", None)
    if not callable(process_pending_fn):
        raise HTTPException(status_code=503, detail="Processador de rescrape não está disponível")

    result = process_pending_fn(limit)
    return RescrapeJobProcessResponseSchema(
        processed_count=result.processed_count,
        completed_count=result.completed_count,
        error_count=result.error_count,
        jobs=[RescrapeJobResponseSchema.model_validate(job.__dict__) for job in result.jobs],
    )

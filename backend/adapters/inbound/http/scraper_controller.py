"""
Scraper Controller - Inbound HTTP Adapter
Operational endpoints: run, status, full config
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from application.domain.services.source_service import SourceService
from configuration.database_configuration import get_db

router = APIRouter(prefix="/api/v1/scrapers", tags=["Scrapers"])


# === Schemas ===

class SourceConfig(BaseModel):
    id: int
    name: str
    enabled: bool
    scraper_base_url: str
    scraper_type: str
    scraper_schedule: str
    extra_config: dict[str, Any]
    analysis: str
    description: str


class ScraperRunQueuedResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    queued_count: int
    submitted_at: datetime
    source_id: Optional[int] = None
    source_name: Optional[str] = None


class ScraperMetricsResponse(BaseModel):
    scraper: str
    runs_total: int
    items_total: int
    errors_total: int
    last_success_at: Optional[str] = None


# === Helpers ===

def _get_services(db: Session = Depends(get_db)):
    return SourceService(persistence=SourcePersistenceAdapter(session=db))


def _build_queued_response(payload: dict, *, source_id: int | None = None, source_name: str | None = None) -> ScraperRunQueuedResponse:
    return ScraperRunQueuedResponse(
        job_id=str(payload["job_id"]),
        status="queued",
        queued_count=int(payload["queued_count"]),
        submitted_at=payload["submitted_at"],
        source_id=source_id,
        source_name=source_name,
    )


# === Endpoints ===

@router.get("/config", response_model=list[SourceConfig])
def get_full_config(enabled_only: bool = True, services=Depends(_get_services)):
    """
    Returns the full scraping configuration tree for job sources.
    """
    sources = services.get_all(enabled_only=enabled_only)

    result = []
    for source in sources:
        result.append(SourceConfig(
            id=source.id,
            name=source.name,
            enabled=source.enabled,
            scraper_base_url=source.scraper_base_url,
            scraper_type=source.scraper_type,
            scraper_schedule=source.scraper_schedule,
            extra_config=source.extra_config or {},
            analysis=source.description,
            description=source.description,
        ))

    return result


@router.get("/status")
def get_scraper_status():
    """Returns lightweight scheduler status."""
    return {"status": "running", "message": "Scheduler active"}


@router.post("/{source_id}/run", response_model=ScraperRunQueuedResponse, status_code=202)
def run_scraper(source_id: int, request: Request, services=Depends(_get_services)):
    """Queue a manual scraper execution for a source and return immediately."""
    source = services.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    if not source.enabled:
        raise HTTPException(status_code=400, detail=f"Source {source.name} is disabled")

    enqueue_run = getattr(request.app.state, "enqueue_manual_source_run", None)
    if not callable(enqueue_run):
        raise HTTPException(status_code=503, detail="Executor manual de scraping não está disponível")

    return _build_queued_response(
        enqueue_run(source.id),
        source_id=source.id,
        source_name=source.name,
    )


@router.post("/run-all", response_model=ScraperRunQueuedResponse, status_code=202)
def run_all_scrapers(request: Request, services=Depends(_get_services)):
    """Queue manual execution for all enabled scrapers and return immediately."""
    sources = services.get_all(enabled_only=True)
    if not sources:
        raise HTTPException(status_code=400, detail="Nenhum scraping ativo disponível para execução manual")

    enqueue_run_all = getattr(request.app.state, "enqueue_manual_run_all", None)
    if not callable(enqueue_run_all):
        raise HTTPException(status_code=503, detail="Executor manual de scraping não está disponível")

    return _build_queued_response(enqueue_run_all(len(sources)))


@router.get("/metrics", response_model=list[ScraperMetricsResponse])
def get_scraper_metrics(request: Request):
    """Return in-memory per-scraper metrics."""
    metrics_service = request.app.state.scraper_metrics_service
    snapshot = metrics_service.snapshot()
    return [
        ScraperMetricsResponse(scraper=name, **values)
        for name, values in snapshot.items()
    ]

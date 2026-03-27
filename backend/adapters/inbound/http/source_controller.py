"""
Source Controller - Inbound HTTP Adapter
"""
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from apscheduler.triggers.cron import CronTrigger
from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from configuration.database_configuration import get_db
from application.domain.entities.source import Source
from application.domain.services.source_service import SourceService
from application.domain.services.scraper_registry import ScraperRegistry
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter

router = APIRouter(prefix="/api/v1/sources", tags=["Sources"])
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


# === Schemas ===

class SourceCreate(BaseModel):
    name: str
    enabled: bool = True
    scraper_base_url: str = ""
    scraper_type: str = "http"
    scraper_schedule: str = "0 */2 * * *"
    extra_config: dict[str, Any] = Field(default_factory=dict)
    analysis: Optional[str] = None
    description: Optional[str] = None


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    scraper_base_url: Optional[str] = None
    scraper_type: Optional[str] = None
    scraper_schedule: Optional[str] = None
    extra_config: Optional[dict[str, Any]] = None
    analysis: Optional[str] = None
    description: Optional[str] = None


class SourceAnalysisUpdate(BaseModel):
    analysis: str


class SourceResponse(BaseModel):
    id: int
    name: str
    enabled: bool
    scraper_base_url: str
    scraper_type: str
    scraper_schedule: str
    extra_config: dict[str, Any]
    analysis: str
    description: str
    last_extraction_status: Optional[str] = None
    last_extraction_http_status: Optional[int] = None
    last_extraction_message: Optional[str] = None
    last_extraction_at: Optional[str] = None
    next_scheduled_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# === Helpers ===

def _get_service(db: Session = Depends(get_db)) -> SourceService:
    adapter = SourcePersistenceAdapter(session=db)
    return SourceService(persistence=adapter)


def _to_response(source: Source) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        name=source.name,
        enabled=source.enabled,
        scraper_base_url=source.scraper_base_url,
        scraper_type=source.scraper_type,
        scraper_schedule=source.scraper_schedule,
        extra_config=source.extra_config or {},
        analysis=source.description,
        description=source.description,
        last_extraction_status=source.last_extraction_status,
        last_extraction_http_status=source.last_extraction_http_status,
        last_extraction_message=source.last_extraction_message,
        last_extraction_at=source.last_extraction_at.isoformat() if source.last_extraction_at else None,
        next_scheduled_at=_compute_next_scheduled_at(source),
        created_at=source.created_at.isoformat() if source.created_at else None,
        updated_at=source.updated_at.isoformat() if source.updated_at else None,
    )


def _compute_next_scheduled_at(
    source: Source,
    *,
    reference_time: Optional[datetime] = None,
) -> Optional[str]:
    if not source.enabled or not source.scraper_schedule:
        return None

    parts = source.scraper_schedule.split()
    if len(parts) != 5:
        return None

    try:
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=SAO_PAULO_TZ,
        )
        now = reference_time.astimezone(SAO_PAULO_TZ) if reference_time else datetime.now(SAO_PAULO_TZ)
        next_run = trigger.get_next_fire_time(None, now)
        return next_run.isoformat() if next_run else None
    except Exception:
        return None


def _ensure_registry_loaded() -> None:
    if not ScraperRegistry.get_all_scrapers():
        load_all_scrapers()


def _validate_source_name(name: str) -> str:
    _ensure_registry_loaded()
    normalized = name.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Source name cannot be empty")

    scraper_class = ScraperRegistry.get_scraper_class(normalized)
    if scraper_class is None:
        available = ", ".join(sorted(ScraperRegistry.get_all_scrapers().keys())[:20])
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source name '{normalized}' is not a registered scraper. "
                f"Available examples: {available}"
            ),
        )
    return normalized


def _resolve_analysis(analysis: Optional[str], description: Optional[str]) -> str:
    if analysis is not None:
        return analysis.strip()
    if description is not None:
        return description.strip()
    return ""


def _resolve_extra_config(extra_config: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(extra_config, dict):
        return {}
    return extra_config


# === Endpoints ===

@router.get("", response_model=list[SourceResponse])
def list_sources(enabled_only: bool = False, service: SourceService = Depends(_get_service)):
    sources = service.get_all(enabled_only=enabled_only)
    return [_to_response(s) for s in sources]


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, service: SourceService = Depends(_get_service)):
    source = service.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    return _to_response(source)


@router.post("", response_model=SourceResponse, status_code=201)
def create_source(body: SourceCreate, service: SourceService = Depends(_get_service)):
    try:
        normalized_name = _validate_source_name(body.name)
        source = service.create(Source(
            name=normalized_name,
            enabled=body.enabled,
            scraper_base_url=body.scraper_base_url,
            scraper_type=body.scraper_type,
            scraper_schedule=body.scraper_schedule,
            extra_config=_resolve_extra_config(body.extra_config),
            description=_resolve_analysis(body.analysis, body.description),
        ))
        return _to_response(source)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{source_id}", response_model=SourceResponse)
def update_source(source_id: int, body: SourceUpdate, service: SourceService = Depends(_get_service)):
    existing = service.get_by_id(source_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    if body.name is not None:
        existing.name = _validate_source_name(body.name)
    if body.enabled is not None:
        existing.enabled = body.enabled
    if body.scraper_base_url is not None:
        existing.scraper_base_url = body.scraper_base_url
    if body.scraper_type is not None:
        existing.scraper_type = body.scraper_type
    if body.scraper_schedule is not None:
        existing.scraper_schedule = body.scraper_schedule
    if body.extra_config is not None:
        existing.extra_config = _resolve_extra_config(body.extra_config)
    if body.analysis is not None or body.description is not None:
        existing.description = _resolve_analysis(body.analysis, body.description)

    try:
        updated = service.update(existing)
        return _to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{source_id}/toggle", response_model=SourceResponse)
def toggle_source(source_id: int, service: SourceService = Depends(_get_service)):
    try:
        source = service.toggle(source_id)
        return _to_response(source)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{source_id}/analysis", response_model=SourceResponse)
def update_source_analysis(
    source_id: int,
    body: SourceAnalysisUpdate,
    service: SourceService = Depends(_get_service),
):
    source = service.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    source.description = body.analysis.strip()
    try:
        updated = service.update(source)
        return _to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, service: SourceService = Depends(_get_service)):
    try:
        service.delete(source_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

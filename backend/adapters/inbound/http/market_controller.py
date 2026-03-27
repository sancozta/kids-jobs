"""Market HTTP controller."""
from datetime import datetime
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from adapters.inbound.http.schemas.market_schema import (
    MarketCreateSchema,
    MarketIngestSchema,
    MarketPatchSchema,
    MarketResponseSchema,
    MarketUpdateSchema,
)
from application.domain.entities.market import Market
from application.domain.services.market_service import MarketService
from configuration.di_configuration import get_market_service

router = APIRouter(prefix="/market", tags=["market"])


def _parse_categories_query(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class MarketBulkDeleteSchema(BaseModel):
    item_ids: list[int] = Field(default_factory=list)


class MarketLookupSchema(BaseModel):
    item_ids: list[int] = Field(default_factory=list)


class MarketBulkDeleteResponseSchema(BaseModel):
    job_id: str
    status: str
    queued_count: int
    submitted_at: datetime


@router.post("/", response_model=MarketResponseSchema, status_code=201)
def create_item(
    body: MarketCreateSchema,
    service: MarketService = Depends(get_market_service),
):
    entity = Market(
        source_id=body.source_id,
        category_id=body.category_id,
        url=body.url,
        title=body.title,
        description=body.description,
        price=body.price,
        currency=body.currency,
        location=body.location,
        state=body.state,
        city=body.city,
        zip_code=body.zip_code,
        street=body.street,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        contact_email=body.contact_email,
        images=body.images,
        videos=body.videos,
        documents=body.documents,
        links=body.links,
        attributes=body.attributes,
    )
    return service.create(entity)


@router.get("/count")
def count_items(
    q: Optional[str] = Query(None, description="Text query for title/description"),
    category: Optional[str] = Query(None, description="Filter by category name"),
    categories: Optional[str] = Query(None, description="Comma-separated category names"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source"),
    created_since: Optional[datetime] = Query(None, description="Filter by creation date from"),
    contract_type: Optional[str] = Query(None, description="Filter by contract type"),
    seniority: Optional[str] = Query(None, description="Filter by seniority"),
    has_contact: Optional[bool] = Query(None, description="Filter items that have phone or email"),
    has_salary_range: Optional[bool] = Query(None, description="Filter items that have salary range"),
    software_focus: Optional[bool] = Query(None, description="Filter items classified as software/TI"),
    actionable_now: Optional[bool] = Query(None, description="Filter items operationally actionable now"),
    exclude_disabled_categories: bool = Query(False, description="Exclude items from disabled categories"),
    service: MarketService = Depends(get_market_service),
):
    """Count market items with advanced filters."""
    total = service.count_with_filters(
        text_query=q,
        category=category,
        categories=_parse_categories_query(categories),
        min_price=min_price,
        max_price=max_price,
        currency=currency,
        state=state,
        city=city,
        source=source,
        created_since=created_since,
        contract_type=contract_type,
        seniority=seniority,
        has_contact=has_contact,
        has_salary_range=has_salary_range,
        software_focus=software_focus,
        actionable_now=actionable_now,
        exclude_disabled_categories=exclude_disabled_categories,
    )
    return {"total": total}


@router.post("/lookup", response_model=list[MarketResponseSchema])
def lookup_items(
    body: MarketLookupSchema,
    service: MarketService = Depends(get_market_service),
):
    return service.get_by_ids(body.item_ids)


@router.get("/{item_id:int}", response_model=MarketResponseSchema)
def get_item(
    item_id: int,
    service: MarketService = Depends(get_market_service),
):
    return service.get_by_id(item_id)


@router.get("/", response_model=list[MarketResponseSchema])
def list_items(
    limit: int = Query(default=100, le=500, description="Maximum number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    q: Optional[str] = Query(None, description="Text query for title/description"),
    category: Optional[str] = Query(None, description="Filter by category name"),
    categories: Optional[str] = Query(None, description="Comma-separated category names"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    currency: Optional[str] = Query(None, description="Filter by currency"),
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source"),
    created_since: Optional[datetime] = Query(None, description="Filter by creation date from"),
    contract_type: Optional[str] = Query(None, description="Filter by contract type"),
    seniority: Optional[str] = Query(None, description="Filter by seniority"),
    has_contact: Optional[bool] = Query(None, description="Filter items that have phone or email"),
    has_salary_range: Optional[bool] = Query(None, description="Filter items that have salary range"),
    software_focus: Optional[bool] = Query(None, description="Filter items classified as software/TI"),
    actionable_now: Optional[bool] = Query(None, description="Filter items operationally actionable now"),
    exclude_disabled_categories: bool = Query(False, description="Exclude items from disabled categories"),
    order_by: str = Query(default="created_at", description="Order by field"),
    order_direction: str = Query(default="desc", description="Order direction"),
    service: MarketService = Depends(get_market_service),
):
    """List market items with advanced filters."""
    return service.find_with_filters(
        text_query=q,
        category=category,
        categories=_parse_categories_query(categories),
        min_price=min_price,
        max_price=max_price,
        currency=currency,
        state=state,
        city=city,
        source=source,
        created_since=created_since,
        contract_type=contract_type,
        seniority=seniority,
        has_contact=has_contact,
        has_salary_range=has_salary_range,
        software_focus=software_focus,
        actionable_now=actionable_now,
        exclude_disabled_categories=exclude_disabled_categories,
        order_by=order_by,
        order_direction=order_direction,
        limit=limit,
        offset=offset
    )


@router.put("/{item_id:int}", response_model=MarketResponseSchema)
def update_item(
    item_id: int,
    body: MarketUpdateSchema,
    service: MarketService = Depends(get_market_service),
):
    entity = Market(
        id=item_id,
        source_id=body.source_id,
        category_id=body.category_id,
        url=body.url,
        title=body.title,
        description=body.description,
        price=body.price,
        currency=body.currency or "BRL",
        location=body.location,
        state=body.state,
        city=body.city,
        zip_code=body.zip_code,
        street=body.street,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        contact_email=body.contact_email,
        images=body.images or [],
        videos=body.videos or [],
        documents=body.documents or [],
        links=body.links or [],
        attributes=body.attributes,
    )
    return service.update(entity)


@router.patch("/{item_id:int}", response_model=MarketResponseSchema)
def patch_item(
    item_id: int,
    body: MarketPatchSchema,
    service: MarketService = Depends(get_market_service),
):
    payload = body.model_dump(exclude_unset=True)
    expected_version = payload.pop("expected_version", None)
    submitted_at = payload.pop("submitted_at", None)

    return service.patch(
        item_id=item_id,
        updates=payload,
        expected_version=expected_version,
        submitted_at=submitted_at,
    )


@router.delete("/{item_id:int}", status_code=204)
def delete_item(
    item_id: int,
    service: MarketService = Depends(get_market_service),
):
    service.delete(item_id)


@router.post(
    "/delete-batch",
    response_model=MarketBulkDeleteResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
def delete_items_batch(
    body: MarketBulkDeleteSchema,
    service: MarketService = Depends(get_market_service),
):
    submitted_at = datetime.utcnow()
    deleted_count = service.delete_many(body.item_ids)

    return MarketBulkDeleteResponseSchema(
        job_id=uuid4().hex,
        status="completed",
        queued_count=deleted_count,
        submitted_at=submitted_at,
    )


@router.post("/ingest", response_model=MarketResponseSchema, status_code=201)
def ingest_item(
    body: MarketIngestSchema,
    service: MarketService = Depends(get_market_service),
):
    """Ingesta item no contrato de scraping local."""
    return service.ingest_raw(body.model_dump())


@router.get("/search/", response_model=list[MarketResponseSchema])
def search_items(
    q: str = Query(..., min_length=2, description="Search query"),
    size: int = Query(default=20, le=100, description="Maximum results"),
    service: MarketService = Depends(get_market_service),
):
    """Full-text search across market items."""
    return service.search_items(query=q, size=size)

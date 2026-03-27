"""
Category Controller - Inbound HTTP Adapter
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from sqlalchemy.orm import Session
from configuration.database_configuration import get_db
from application.domain.entities.category import Category
from application.domain.services.category_service import CategoryService
from application.domain.services.source_service import SourceService
from adapters.outbound.persistence.category_persistence_adapter import CategoryPersistenceAdapter
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter

router = APIRouter(prefix="/api/v1", tags=["Categories"])


# === Schemas ===

class CategoryCreate(BaseModel):
    name: str
    scrape_path: Optional[str] = None
    category_id: Optional[int] = None
    schedule: Optional[str] = None
    enabled: bool = True


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    scrape_path: Optional[str] = None
    category_id: Optional[int] = None
    schedule: Optional[str] = None
    enabled: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    source_id: int
    category_id: Optional[int] = None
    scrape_path: Optional[str] = None
    schedule: Optional[str] = None
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# === Helpers ===

def _get_services(db: Session = Depends(get_db)):
    cat_adapter = CategoryPersistenceAdapter(session=db)
    src_adapter = SourcePersistenceAdapter(session=db)
    return CategoryService(persistence=cat_adapter), SourceService(persistence=src_adapter)


def _to_response(category: Category) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        name=category.name,
        source_id=category.source_id,
        category_id=category.category_id,
        scrape_path=category.scrape_path,
        schedule=category.schedule,
        enabled=category.enabled,
        created_at=category.created_at.isoformat() if category.created_at else None,
        updated_at=category.updated_at.isoformat() if category.updated_at else None,
    )


# === Endpoints ===

@router.get("/sources/{source_id}/categories", response_model=list[CategoryResponse])
def list_categories(source_id: int, enabled_only: bool = False, services=Depends(_get_services)):
    cat_service, src_service = services
    source = src_service.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    categories = cat_service.get_by_source_id(source_id, enabled_only=enabled_only)
    return [_to_response(c) for c in categories]


@router.post("/sources/{source_id}/categories", response_model=CategoryResponse, status_code=201)
def create_category(source_id: int, body: CategoryCreate, services=Depends(_get_services)):
    cat_service, src_service = services
    source = src_service.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")

    category = cat_service.create(Category(
        name=body.name,
        source_id=source_id,
        category_id=body.category_id,
        scrape_path=body.scrape_path,
        schedule=body.schedule,
        enabled=body.enabled,
    ))
    return _to_response(category)


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, services=Depends(_get_services)):
    cat_service, _ = services
    category = cat_service.get_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
    return _to_response(category)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, body: CategoryUpdate, services=Depends(_get_services)):
    cat_service, _ = services
    existing = cat_service.get_by_id(category_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")

    if body.name is not None:
        existing.name = body.name
    if body.scrape_path is not None:
        existing.scrape_path = body.scrape_path
    if body.category_id is not None:
        existing.category_id = body.category_id
    if body.schedule is not None:
        existing.schedule = body.schedule
    if body.enabled is not None:
        existing.enabled = body.enabled

    try:
        updated = cat_service.update(existing)
        return _to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, services=Depends(_get_services)):
    cat_service, _ = services
    try:
        cat_service.delete(category_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

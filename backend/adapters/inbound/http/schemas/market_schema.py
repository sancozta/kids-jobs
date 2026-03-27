"""
Market Schemas - Pydantic models for API
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MarketResponseSchema(BaseModel):
    """Market response schema"""
    id: int = Field(..., description="ID unico da oportunidade")
    source_id: Optional[int] = Field(None, description="ID da fonte")
    category_id: Optional[int] = Field(None, description="ID da categoria")
    url: Optional[str] = Field(None, description="URL da oportunidade")
    title: Optional[str] = Field(None, description="Titulo da oportunidade")
    description: Optional[str] = Field(None, description="Descricao detalhada")
    price: Optional[float] = Field(None, description="Preco")
    currency: Optional[str] = Field(None, description="Moeda (BRL, USD, etc)")
    location: Optional[Dict[str, Any]] = Field(None, description="Localizacao estruturada")

    # Endereco
    state: Optional[str] = Field(None, description="Estado (UF)")
    city: Optional[str] = Field(None, description="Cidade")
    zip_code: Optional[str] = Field(None, description="CEP")
    street: Optional[str] = Field(None, description="Rua/Endereco")

    # Contato
    contact_name: Optional[str] = Field(None, description="Nome do contato")
    contact_phone: Optional[str] = Field(None, description="Telefone do contato")
    contact_email: Optional[str] = Field(None, description="Email do contato")

    # Midia
    images: List[str] = Field(default_factory=list, description="URLs de imagens")
    videos: List[str] = Field(default_factory=list, description="URLs de videos")
    documents: List[str] = Field(default_factory=list, description="URLs de documentos")
    links: List[str] = Field(default_factory=list, description="Links relacionados")

    # Extras
    attributes: Optional[Dict[str, Any]] = Field(None, description="Atributos customizados")
    version: int = Field(1, description="Versao do registro")

    created_at: Optional[datetime] = Field(None, description="Data/hora de criacao")
    updated_at: Optional[datetime] = Field(None, description="Data/hora da ultima atualizacao")

    class Config:
        from_attributes = True


class MarketCreateSchema(BaseModel):
    """Market creation schema"""
    source_id: Optional[int] = Field(None, description="ID da fonte")
    category_id: Optional[int] = Field(None, description="ID da categoria")
    url: Optional[str] = Field(None, description="URL unica")
    title: Optional[str] = Field(None, description="Titulo")
    description: Optional[str] = Field(None, description="Descricao")
    price: Optional[float] = Field(None, ge=0, description="Preco")
    currency: str = Field(default="BRL", description="Moeda")
    location: Optional[Dict[str, Any]] = Field(None, description="Localizacao estruturada")
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    videos: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    attributes: Optional[Dict[str, Any]] = Field(None, description="Atributos customizados")


class MarketUpdateSchema(BaseModel):
    """Market update schema"""
    source_id: Optional[int] = None
    category_id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    images: Optional[List[str]] = None
    videos: Optional[List[str]] = None
    documents: Optional[List[str]] = None
    links: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None


class MarketPatchSchema(BaseModel):
    """Partial market update schema with optimistic concurrency options"""

    expected_version: Optional[int] = Field(None, ge=1, description="Versao esperada do registro")
    submitted_at: Optional[datetime] = Field(None, description="Data/hora em que a analise foi solicitada")

    source_id: Optional[int] = None
    category_id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    images: Optional[List[str]] = None
    videos: Optional[List[str]] = None
    documents: Optional[List[str]] = None
    links: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None


class MarketIngestSchema(BaseModel):
    """Schema do contrato de scraping local usado pelo kids-jobs."""
    url: str = Field(..., description="URL da oportunidade")
    source: Dict[str, Any] = Field(..., description="Dados da fonte")
    category: Dict[str, Any] = Field(..., description="Dados da categoria")
    scraped_data: Dict[str, Any] = Field(default_factory=dict, description="Dados extraidos")
    version: Optional[int] = Field(None, description="Versao do scraper")

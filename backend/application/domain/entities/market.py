"""
Market - Domain Entity
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Market:
    """Oportunidade de mercado"""

    # References
    url: str = ""
    source_id: Optional[int] = None
    category_id: Optional[int] = None

    # Dados do anuncio
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "BRL"
    location: Optional[dict] = field(default_factory=dict)

    # Endereco
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None

    # Contato
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    # Midia
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    # Dados extras
    attributes: Optional[dict] = field(default_factory=dict)

    # Versao
    version: int = 1

    # Identificacao
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

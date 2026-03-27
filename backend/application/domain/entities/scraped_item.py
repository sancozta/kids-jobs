"""
Scraped Item Entity - Contract Format
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    """Dados de geolocalização"""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass
class ScrapedData:
    """Dados extraídos pelo scraper"""

    # Anúncio
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "BRL"

    # Localização
    location: Optional[Location] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    street: Optional[str] = None

    # Contato
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    # Mídia
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    # Dados extras
    attributes: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "location": self.location.to_dict() if self.location else {},
            "state": self.state,
            "city": self.city,
            "zip_code": self.zip_code,
            "street": self.street,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "images": self.images,
            "videos": self.videos,
            "documents": self.documents,
            "links": self.links,
            "attributes": self.attributes,
        }


@dataclass
class ScrapedItem:
    """Item coletado por um scraper — formato que vai para RabbitMQ"""

    # Identifiers
    url: str

    # Source/Category references
    source_id: int = 0
    source_name: str = ""
    category_id: int = 0
    category_name: str = ""

    # Extracted data
    scraped_data: ScrapedData = field(default_factory=ScrapedData)

    def to_dict(self) -> dict:
        """Serializes to the contract format for RabbitMQ"""
        return {
            "url": self.url,
            "source": {
                "id": self.source_id,
                "name": self.source_name,
            },
            "category": {
                "id": self.category_id,
                "name": self.category_name,
            },
            "scraped_data": self.scraped_data.to_dict(),
        }

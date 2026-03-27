"""Market model for SQLite-backed kids-jobs."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text

from application.domain.entities.market import Market
from configuration.database_configuration import Base


class MarketModel(Base):
    __tablename__ = "sc_market"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(10), default="BRL")
    location = Column(JSON, nullable=True)
    state = Column(String(2), nullable=True, index=True)
    city = Column(String(255), nullable=True, index=True)
    zip_code = Column(String(10), nullable=True)
    street = Column(String(500), nullable=True)
    contact_name = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    images = Column(JSON, nullable=False, default=list)
    videos = Column(JSON, nullable=False, default=list)
    documents = Column(JSON, nullable=False, default=list)
    links = Column(JSON, nullable=False, default=list)
    attributes = Column(JSON, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_entity(self) -> Market:
        return Market(
            id=self.id,
            url=self.url,
            source_id=self.source_id,
            category_id=self.category_id,
            title=self.title,
            description=self.description,
            price=self.price,
            currency=self.currency,
            location=self.location or {},
            state=self.state,
            city=self.city,
            zip_code=self.zip_code,
            street=self.street,
            contact_name=self.contact_name,
            contact_phone=self.contact_phone,
            contact_email=self.contact_email,
            images=list(self.images or []),
            videos=list(self.videos or []),
            documents=list(self.documents or []),
            links=list(self.links or []),
            attributes=self.attributes or {},
            version=self.version or 1,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_entity(entity: Market) -> "MarketModel":
        return MarketModel(
            id=entity.id,
            url=entity.url,
            source_id=entity.source_id,
            category_id=entity.category_id,
            title=entity.title,
            description=entity.description,
            price=entity.price,
            currency=entity.currency,
            location=entity.location or {},
            state=entity.state,
            city=entity.city,
            zip_code=entity.zip_code,
            street=entity.street,
            contact_name=entity.contact_name,
            contact_phone=entity.contact_phone,
            contact_email=entity.contact_email,
            images=list(entity.images or []),
            videos=list(entity.videos or []),
            documents=list(entity.documents or []),
            links=list(entity.links or []),
            attributes=entity.attributes or {},
            version=entity.version,
        )

"""Local messaging adapter that ingests scraper output into the same SQLite database."""
from __future__ import annotations

from adapters.outbound.persistence.category_persistence_adapter import CategoryPersistenceAdapter
from adapters.outbound.persistence.market_persistence_adapter import MarketPersistenceAdapter
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from application.domain.services.category_service import CategoryService
from application.domain.services.market_service import MarketService
from application.domain.services.source_service import SourceService
from application.ports.outbound.messaging.messaging_port import MessagingPort
from application.domain.entities.scraped_item import ScrapedItem
from configuration.database_configuration import SessionLocal


class LocalIngestAdapter(MessagingPort):
    """Persist scraped items locally instead of publishing them to RabbitMQ."""

    def publish(self, item: ScrapedItem, routing_key: str) -> None:
        db = SessionLocal()
        try:
            service = MarketService(
                repository=MarketPersistenceAdapter(session=db),
                source_service=SourceService(persistence=SourcePersistenceAdapter(session=db)),
                category_service=CategoryService(persistence=CategoryPersistenceAdapter(session=db)),
            )
            service.ingest_raw(item.to_dict())
        finally:
            db.close()

"""SQLite database configuration for kids-jobs."""
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker

from configuration.settings_configuration import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and apply lightweight additive migrations."""
    from adapters.outbound.persistence.models.category_model import CategoryModel  # noqa: F401
    from adapters.outbound.persistence.models.market_model import MarketModel  # noqa: F401
    from adapters.outbound.persistence.models.rescrape_job_model import RescrapeJobModel  # noqa: F401
    from adapters.outbound.persistence.models.resume_document_model import ResumeDocumentModel  # noqa: F401
    from adapters.outbound.persistence.models.source_execution_history_model import SourceExecutionHistoryModel  # noqa: F401
    from adapters.outbound.persistence.models.source_model import SourceModel  # noqa: F401
    from adapters.outbound.persistence.models.telegram_offset_model import TelegramOffsetModel  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_migrations()


def _run_sqlite_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    migrations = {
        "categories": [
            ("category_id", "ALTER TABLE categories ADD COLUMN category_id INTEGER"),
            ("scrape_path", "ALTER TABLE categories ADD COLUMN scrape_path VARCHAR"),
        ],
        "sources": [
            ("scraper_base_url", "ALTER TABLE sources ADD COLUMN scraper_base_url VARCHAR"),
            ("scraper_type", "ALTER TABLE sources ADD COLUMN scraper_type VARCHAR DEFAULT 'http'"),
            ("scraper_schedule", "ALTER TABLE sources ADD COLUMN scraper_schedule VARCHAR DEFAULT '0 */2 * * *'"),
            ("extra_config", "ALTER TABLE sources ADD COLUMN extra_config TEXT DEFAULT '{}'"),
            ("description", "ALTER TABLE sources ADD COLUMN description TEXT DEFAULT ''"),
            ("last_extraction_status", "ALTER TABLE sources ADD COLUMN last_extraction_status VARCHAR"),
            ("last_extraction_http_status", "ALTER TABLE sources ADD COLUMN last_extraction_http_status INTEGER"),
            ("last_extraction_message", "ALTER TABLE sources ADD COLUMN last_extraction_message TEXT"),
            ("last_extraction_at", "ALTER TABLE sources ADD COLUMN last_extraction_at DATETIME"),
        ],
        "sc_market": [
            ("videos", "ALTER TABLE sc_market ADD COLUMN videos JSON"),
            ("documents", "ALTER TABLE sc_market ADD COLUMN documents JSON"),
            ("links", "ALTER TABLE sc_market ADD COLUMN links JSON"),
            ("attributes", "ALTER TABLE sc_market ADD COLUMN attributes JSON"),
            ("version", "ALTER TABLE sc_market ADD COLUMN version INTEGER DEFAULT 1"),
        ],
    }

    with engine.begin() as connection:
        for table, table_migrations in migrations.items():
            rows = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if not rows:
                continue

            existing_columns = {str(row[1]) for row in rows}
            for column_name, statement in table_migrations:
                if column_name not in existing_columns:
                    connection.execute(text(statement))

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
    """Create all tables and apply lightweight SQLite migrations."""
    _run_sqlite_legacy_table_migrations()

    from adapters.outbound.persistence.models.market_model import MarketModel  # noqa: F401
    from adapters.outbound.persistence.models.rescrape_job_model import RescrapeJobModel  # noqa: F401
    from adapters.outbound.persistence.models.resume_document_model import ResumeDocumentModel  # noqa: F401
    from adapters.outbound.persistence.models.source_execution_history_model import SourceExecutionHistoryModel  # noqa: F401
    from adapters.outbound.persistence.models.source_model import SourceModel  # noqa: F401
    from adapters.outbound.persistence.models.telegram_offset_model import TelegramOffsetModel  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_sqlite_migrations()


def _sqlite_table_exists(connection, table_name: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name = :table_name"),
        {"table_name": table_name},
    ).fetchone()
    return row is not None


def _sqlite_columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {str(row[1]) for row in rows}


def _run_sqlite_legacy_table_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        legacy_renames = {
            "sc_market": "jobs",
            "gr_resume_documents": "resume_documents",
            "sc_rescrape_jobs": "rescrape_jobs",
        }

        for old_name, new_name in legacy_renames.items():
            if _sqlite_table_exists(connection, old_name) and not _sqlite_table_exists(connection, new_name):
                connection.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))


def _rebuild_jobs_table_without_category(connection) -> None:
    if not _sqlite_table_exists(connection, "jobs"):
        return

    existing_columns = _sqlite_columns(connection, "jobs")
    if "category_id" not in existing_columns:
        return

    connection.execute(text("ALTER TABLE jobs RENAME TO jobs_legacy"))
    connection.execute(
        text(
            """
            CREATE TABLE jobs (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                url VARCHAR(2048) NOT NULL,
                source_id INTEGER,
                title VARCHAR(500),
                description TEXT,
                price FLOAT,
                currency VARCHAR(10),
                location JSON,
                state VARCHAR(2),
                city VARCHAR(255),
                zip_code VARCHAR(10),
                street VARCHAR(500),
                contact_name VARCHAR(255),
                contact_phone VARCHAR(20),
                contact_email VARCHAR(255),
                images JSON NOT NULL DEFAULT '[]',
                videos JSON NOT NULL DEFAULT '[]',
                documents JSON NOT NULL DEFAULT '[]',
                links JSON NOT NULL DEFAULT '[]',
                attributes JSON,
                version INTEGER DEFAULT 1,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(source_id) REFERENCES sources (id)
            )
            """
        )
    )
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_jobs_url ON jobs (url)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_source_id ON jobs (source_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_state ON jobs (state)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_city ON jobs (city)"))

    legacy_columns = _sqlite_columns(connection, "jobs_legacy")
    copy_columns = [
        "id",
        "url",
        "source_id",
        "title",
        "description",
        "price",
        "currency",
        "location",
        "state",
        "city",
        "zip_code",
        "street",
        "contact_name",
        "contact_phone",
        "contact_email",
        "images",
        "videos",
        "documents",
        "links",
        "attributes",
        "version",
        "created_at",
        "updated_at",
    ]
    preserved_columns = [column for column in copy_columns if column in legacy_columns]
    if preserved_columns:
        columns_sql = ", ".join(preserved_columns)
        connection.execute(text(f"INSERT INTO jobs ({columns_sql}) SELECT {columns_sql} FROM jobs_legacy"))

    connection.execute(text("DROP TABLE jobs_legacy"))


def _run_sqlite_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    migrations = {
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
        "jobs": [
            ("videos", "ALTER TABLE jobs ADD COLUMN videos JSON"),
            ("documents", "ALTER TABLE jobs ADD COLUMN documents JSON"),
            ("links", "ALTER TABLE jobs ADD COLUMN links JSON"),
            ("attributes", "ALTER TABLE jobs ADD COLUMN attributes JSON"),
            ("version", "ALTER TABLE jobs ADD COLUMN version INTEGER DEFAULT 1"),
        ],
    }

    with engine.begin() as connection:
        _rebuild_jobs_table_without_category(connection)

        for table, table_migrations in migrations.items():
            if not _sqlite_table_exists(connection, table):
                continue

            existing_columns = _sqlite_columns(connection, table)
            for column_name, statement in table_migrations:
                if column_name not in existing_columns:
                    connection.execute(text(statement))

        if _sqlite_table_exists(connection, "categories"):
            connection.execute(text("DROP TABLE categories"))

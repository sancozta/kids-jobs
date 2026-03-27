"""
Seed scraping sources from scraper registry.
Usage:
    python scripts/seed_sources.py
"""
from __future__ import annotations

from copy import deepcopy
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.outbound.persistence.category_persistence_adapter import CategoryPersistenceAdapter
from adapters.outbound.persistence.source_persistence_adapter import SourcePersistenceAdapter
from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from application.domain.entities.category import Category
from application.domain.entities.source import Source
from application.domain.services.scraper_registry import ScraperRegistry
from application.domain.shared.scraper_types import SourceType
from configuration.database_configuration import SessionLocal, init_db

DEFAULT_SCHEDULE = "0 */6 * * *"
DEPRECATED_SOURCES = {
    "chaozao",
    "copart",
    "deprol",
    "dfimoveis",
    "farmaful",
    "geekhunter",
    "icarros",
    "imovelweb",
    "indeed",
    "kavak",
    "lascolonias",
    "loft",
    "megaleiloes",
    "mfrural",
    "mobiauto",
    "nutrada",
    "oemed",
    "olx_imoveis",
    "olx_vehicles",
    "pncp_licitacoes",
    "portalzuk",
    "pronutrition",
    "quintoandar",
    "sodresantoro",
    "superbid",
    "vagas",
    "vivareal",
    "webmotors",
    "zapimoveis",
}
PRIMARY_CATEGORY_LABELS = {
    "jobs": "EMPREGOS",
    "general": "GERAL",
}


def _merge_extra_config(*, desired: dict | None, existing: dict | None) -> dict:
    merged = deepcopy(desired or {})
    if isinstance(existing, dict) and existing:
        merged.update(deepcopy(existing))
    return merged


def _get_primary_category_label(category_value: str | None) -> str | None:
    if not category_value:
        return None
    return PRIMARY_CATEGORY_LABELS.get(category_value, category_value.replace("_", " ").upper())


def seed_sources() -> dict[str, int]:
    """Create or update sources for every registered scraper (idempotent)."""
    init_db()
    load_all_scrapers()

    created = 0
    updated = 0
    skipped = 0
    removed = 0
    categories_created = 0
    categories_updated = 0

    db = SessionLocal()
    try:
        adapter = SourcePersistenceAdapter(session=db)
        category_adapter = CategoryPersistenceAdapter(session=db)

        for scraper_name in sorted(ScraperRegistry.get_all_scrapers().keys()):
            config = ScraperRegistry.get_config(scraper_name)
            existing = adapter.find_by_name(scraper_name)

            desired_base_url = config.base_url if config else ""
            desired_type = config.strategy.value if config and config.strategy else "http_basic"
            if config and getattr(config.metadata, "source_type", None) == SourceType.TELEGRAM:
                desired_type = "telegram"
            desired_schedule = (config.schedule or DEFAULT_SCHEDULE) if config else DEFAULT_SCHEDULE
            desired_enabled = config.enabled if config else True
            desired_extra_config = deepcopy(config.extra_config) if config and isinstance(config.extra_config, dict) else {}
            desired_primary_category = _get_primary_category_label(
                config.metadata.category.value if config and config.metadata.category else None
            )

            if existing:
                changed = False
                if existing.scraper_base_url != desired_base_url:
                    existing.scraper_base_url = desired_base_url
                    changed = True
                if existing.scraper_type != desired_type:
                    existing.scraper_type = desired_type
                    changed = True
                if existing.scraper_schedule != desired_schedule:
                    existing.scraper_schedule = desired_schedule
                    changed = True
                merged_extra_config = _merge_extra_config(
                    desired=desired_extra_config,
                    existing=existing.extra_config,
                )
                if existing.extra_config != merged_extra_config:
                    existing.extra_config = merged_extra_config
                    changed = True
                # Preserve manual operational state from the DB for existing sources.
                if changed:
                    adapter.update(existing)
                    updated += 1
                else:
                    skipped += 1
                source = existing
            else:
                source = adapter.save(
                    Source(
                        name=scraper_name,
                        enabled=desired_enabled,
                        scraper_base_url=desired_base_url or "",
                        scraper_type=desired_type or "http",
                        scraper_schedule=desired_schedule or DEFAULT_SCHEDULE,
                        extra_config=desired_extra_config,
                    )
                )
                created += 1

            if desired_primary_category:
                categories = category_adapter.find_by_source_id(source.id or 0, enabled_only=False)
                primary = next((item for item in categories if (item.name or "").strip().upper() == desired_primary_category), None)

                if primary is None and not categories:
                    category_adapter.save(
                        Category(
                            name=desired_primary_category,
                            source_id=source.id or 0,
                            enabled=True,
                        )
                    )
                    categories_created += 1
                elif primary is None and len(categories) == 1 and not categories[0].scrape_path and not categories[0].schedule:
                    category = categories[0]
                    if category.name != desired_primary_category:
                        category.name = desired_primary_category
                        category.enabled = True
                        category_adapter.update(category)
                        categories_updated += 1
                elif primary is not None and not primary.enabled:
                    primary.enabled = True
                    category_adapter.update(primary)
                    categories_updated += 1

        for deprecated_name in sorted(DEPRECATED_SOURCES):
            deprecated = adapter.find_by_name(deprecated_name)
            if not deprecated or deprecated.id is None:
                continue
            for category in category_adapter.find_by_source_id(deprecated.id, enabled_only=False):
                if category.id is not None:
                    category_adapter.delete(category.id)
            adapter.delete(deprecated.id)
            removed += 1

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "removed": removed,
            "categories_created": categories_created,
            "categories_updated": categories_updated,
        }
    finally:
        db.close()


def main() -> None:
    result = seed_sources()
    print(result)


if __name__ == "__main__":
    main()

from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.scraper_loader import load_all_scrapers
from adapters.outbound.scraping.base_scraper import BaseScraper
from application.domain.services.scraper_factory import ScraperFactory
from application.domain.services.scraper_registry import ScraperRegistry


def _registered_scrapers() -> list[str]:
    load_all_scrapers()
    return sorted(ScraperRegistry.get_all_scrapers().keys())


@pytest.mark.quickcheck
@pytest.mark.parametrize("scraper_name", _registered_scrapers())
def test_scraper_quickcheck_handles_empty_fetch(monkeypatch: pytest.MonkeyPatch, scraper_name: str) -> None:
    """
    Quickcheck offline: garante que cada scraper pode ser instanciado e executado
    sem rede, retornando uma lista (mesmo vazia), sem estourar exceção.
    """
    scraper = ScraperFactory.create(scraper_name)
    assert scraper is not None, f"{scraper_name}: scraper não encontrado no registry"

    if hasattr(scraper, "fetch_page"):
        monkeypatch.setattr(scraper, "fetch_page", lambda *args, **kwargs: None)
    if hasattr(scraper, "fetch_json"):
        monkeypatch.setattr(scraper, "fetch_json", lambda *args, **kwargs: None)

    items = scraper.scrape()
    assert isinstance(items, list), f"{scraper_name}: scrape() deve retornar list[ScrapedItem]"


@pytest.mark.quickcheck
@pytest.mark.parametrize("scraper_name", _registered_scrapers())
def test_scraper_quickcheck_exposes_rescrape_entrypoint(monkeypatch: pytest.MonkeyPatch, scraper_name: str) -> None:
    """
    Garante que todo scraper registrado possui entrada funcional para rescrape.

    Mesmo quando o scraper não sobrescreve `scrape_url(url)`, o fallback do
    `BaseScraper` deve existir e retornar `None` sem estourar exceção em modo offline.
    """
    scraper = ScraperFactory.create(scraper_name)
    assert scraper is not None, f"{scraper_name}: scraper não encontrado no registry"

    if hasattr(scraper, "fetch_page"):
        monkeypatch.setattr(scraper, "fetch_page", lambda *args, **kwargs: None)
    if hasattr(scraper, "fetch_json"):
        monkeypatch.setattr(scraper, "fetch_json", lambda *args, **kwargs: None)

    item = scraper.scrape_url("https://example.com/item/1")
    assert item is None or hasattr(item, "url"), f"{scraper_name}: scrape_url() deve retornar ScrapedItem | None"


@pytest.mark.quickcheck
@pytest.mark.parametrize("scraper_name", _registered_scrapers())
def test_scraper_quickcheck_requires_custom_scrape_url_for_jobs(scraper_name: str) -> None:
    scraper = ScraperFactory.create(scraper_name)
    assert scraper is not None, f"{scraper_name}: scraper não encontrado no registry"

    config = scraper.get_config()
    category = getattr(getattr(config, "metadata", None), "category", None)
    if str(category).lower() != "jobs":
        return

    implementation = type(scraper).__dict__.get("scrape_url")
    assert implementation is not None and implementation is not BaseScraper.scrape_url, (
        f"{scraper_name}: scrapers de jobs devem sobrescrever scrape_url(url) "
        "para reprocessamento determinístico por URL"
    )

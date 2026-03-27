from types import SimpleNamespace

import scripts.seed_sources as seed_module
from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.entities.source import Source
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


def _build_config(*, name: str = "dummy", enabled: bool = True) -> ScraperConfig:
    return ScraperConfig(
        metadata=ScraperMetadata(
            name=name,
            display_name=name.upper(),
            description="Teste",
            category=ScrapingCategory.VEHICLES,
            source_type=SourceType.HTTP,
        ),
        base_url="https://example.com",
        endpoint="/items",
        enabled=enabled,
        schedule="0 */6 * * *",
    )


class _FakeDbSession:
    def close(self) -> None:
        return None


class _FakeSourceAdapter:
    existing_source: Source | None = None
    saved_sources: list[Source] = []
    updated_sources: list[Source] = []

    def __init__(self, session):
        self.session = session

    def find_by_name(self, name: str) -> Source | None:
        return self.__class__.existing_source

    def save(self, source: Source) -> Source:
        if source.id is None:
            source.id = 999
        self.__class__.saved_sources.append(source)
        return source

    def update(self, source: Source) -> Source:
        self.__class__.updated_sources.append(source)
        return source

    def delete(self, source_id: int) -> None:
        return None


def _patch_seed_dependencies(monkeypatch, *, config: ScraperConfig) -> None:
    _FakeSourceAdapter.saved_sources = []
    _FakeSourceAdapter.updated_sources = []

    monkeypatch.setattr(seed_module, "init_db", lambda: None)
    monkeypatch.setattr(seed_module, "load_all_scrapers", lambda: None)
    monkeypatch.setattr(seed_module, "SessionLocal", lambda: _FakeDbSession())
    monkeypatch.setattr(seed_module, "SourcePersistenceAdapter", _FakeSourceAdapter)
    monkeypatch.setattr(
        seed_module,
        "ScraperRegistry",
        SimpleNamespace(
            get_all_scrapers=lambda: {config.metadata.name: object()},
            get_config=lambda scraper_name: config,
        ),
    )


def test_seed_sources_preserves_existing_enabled_state(monkeypatch) -> None:
    config = _build_config(enabled=True)
    existing = Source(
        id=1,
        name=config.metadata.name,
        enabled=False,
        scraper_base_url="https://old.example.com",
        scraper_type="http_basic",
        scraper_schedule="0 0 * * *",
    )
    _FakeSourceAdapter.existing_source = existing
    _patch_seed_dependencies(monkeypatch, config=config)

    result = seed_module.seed_sources()

    assert result["updated"] == 1
    assert existing.enabled is False
    assert _FakeSourceAdapter.updated_sources[0].enabled is False


def test_seed_sources_uses_config_enabled_for_new_source(monkeypatch) -> None:
    config = _build_config(name="vehicles_disabled", enabled=False)
    _FakeSourceAdapter.existing_source = None
    _patch_seed_dependencies(monkeypatch, config=config)

    result = seed_module.seed_sources()

    assert result["created"] == 1
    assert _FakeSourceAdapter.saved_sources[0].enabled is False

def test_seed_sources_persists_extra_config_for_new_source(monkeypatch) -> None:
    config = _build_config(name="pncp_licitacoes")
    config.metadata.category = ScrapingCategory.TENDERS
    config.metadata.source_type = SourceType.API
    config.extra_config = {
        "target_ufs": ["SP", "RJ"],
        "target_municipios_ibge": ["3550308"],
    }
    _FakeSourceAdapter.existing_source = None
    _patch_seed_dependencies(monkeypatch, config=config)

    seed_module.seed_sources()

    assert _FakeSourceAdapter.saved_sources[0].extra_config == {
        "target_ufs": ["SP", "RJ"],
        "target_municipios_ibge": ["3550308"],
    }

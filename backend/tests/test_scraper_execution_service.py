from application.domain.entities.scraper_config import ScraperConfig, ScraperMetadata
from application.domain.entities.source import Source
from application.domain.services.scraper_execution_service import (
    ScraperExecutionService,
    SourceExecutionResult,
)
from application.domain.shared.scraper_types import ScrapingCategory, SourceType


def _result(**overrides) -> SourceExecutionResult:
    base = dict(
        source_id=2,
        source_name="chaozao",
        success=True,
        scraped_count=10,
        published_count=10,
        duration_ms=1200,
        strategy="browser_playwright",
        http_status_code=200,
        error=None,
    )
    base.update(overrides)
    return SourceExecutionResult(**base)


def test_classify_success_when_all_scraped_items_are_published() -> None:
    result = _result(scraped_count=25, published_count=25, success=True)
    assert ScraperExecutionService.classify_extraction_status(result) == "SUCCESS"
    assert ScraperExecutionService.build_extraction_message(result) == "Extraído e publicado (25/25 itens)"


def test_classify_partial_when_only_part_of_items_are_published() -> None:
    result = _result(scraped_count=25, published_count=7, success=True)
    assert ScraperExecutionService.classify_extraction_status(result) == "PARTIAL"
    assert ScraperExecutionService.build_extraction_message(result) == "Extração/publicação parcial (7/25 itens)"


def test_classify_error_when_no_item_is_published() -> None:
    result = _result(scraped_count=25, published_count=0, success=False, error="Falha ao publicar itens no RabbitMQ")
    assert ScraperExecutionService.classify_extraction_status(result) == "ERROR"
    assert ScraperExecutionService.build_extraction_message(result) == "Falha ao publicar itens no RabbitMQ"


def test_apply_source_overrides_to_config_merges_extra_config() -> None:
    config = ScraperConfig(
        metadata=ScraperMetadata(
            name="pncp_licitacoes",
            display_name="PNCP Licitações",
            description="Teste",
            category=ScrapingCategory.TENDERS,
            source_type=SourceType.API,
        ),
        base_url="https://pncp.gov.br/api/consulta",
        extra_config={"target_ufs": [], "target_municipios_ibge": []},
    )
    source = Source(
        name="pncp_licitacoes",
        scraper_type="http_basic",
        scraper_schedule="0 */6 * * *",
        extra_config={
            "target_ufs": ["SP", "RJ"],
            "target_municipios_ibge": ["3550308"],
        },
    )

    strategy = ScraperExecutionService.apply_source_overrides_to_config(config, source)

    assert strategy.value == "http_basic"
    assert config.extra_config["target_ufs"] == ["SP", "RJ"]
    assert config.extra_config["target_municipios_ibge"] == ["3550308"]

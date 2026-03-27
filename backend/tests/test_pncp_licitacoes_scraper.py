from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.tenders.pncp_licitacoes_scraper import (
    PNCPLicitacoesScraper,
)
from application.domain.entities.scraper_config import ScraperConfig


class _TestPNCPLicitacoesScraper(PNCPLicitacoesScraper):
    def __init__(self, responses: dict[str, dict | None], *, config: ScraperConfig | None = None):
        super().__init__(config=config)
        self._responses = responses

    def fetch_json(self, endpoint: str, method: str = "GET", params=None, json_data=None, **kwargs):  # type: ignore[override]
        key = self._build_lookup_key(endpoint=endpoint, params=params)
        response = self._responses.get(key)
        self.last_fetch_diagnostics = {
            "status_code": 200 if response is not None else 404,
            "error": None if response is not None else "not found",
            "url": key,
        }
        return response

    @staticmethod
    def _build_lookup_key(*, endpoint: str, params=None) -> str:
        if endpoint == "/v1/contratacoes/proposta" and isinstance(params, dict):
            parts = [f"pagina={params.get('pagina')}"]
            if params.get("uf"):
                parts.append(f"uf={params.get('uf')}")
            if params.get("codigoMunicipioIbge"):
                parts.append(f"codigoMunicipioIbge={params.get('codigoMunicipioIbge')}")
            return f"{endpoint}?{'&'.join(parts)}"
        return endpoint


def test_pncp_licitacoes_scraper_parses_open_listing() -> None:
    config = PNCPLicitacoesScraper.get_default_config()
    config.extra_config = {
        "target_ufs": [],
        "target_municipios_ibge": [],
    }
    scraper = _TestPNCPLicitacoesScraper(
        {
            "/v1/contratacoes/proposta?pagina=1": {
                "data": [
                    {
                        "numeroControlePNCP": "45370087000127-1-000008/2026",
                        "numeroCompra": "002",
                        "processo": "003",
                        "objetoCompra": "CONTRATAÇÃO DE LEILOEIRO PÚBLICO PARA REALIZAÇÃO DE LEILÃO.",
                        "valorTotalEstimado": 5.0,
                        "dataPublicacaoPncp": "2026-03-01T23:52:10",
                        "dataAberturaProposta": "2026-03-01T23:49:00",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Pregão - Eletrônico",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "modoDisputaNome": "Aberto",
                        "tipoInstrumentoConvocatorioNome": "Edital",
                        "amparoLegal": {"descricao": "Lei 14.133/2021"},
                        "srp": True,
                        "orcamentoSigilosoDescricao": "Não",
                        "fontesOrcamentarias": [{"codigo": "1"}, {"codigo": "2"}],
                        "linkSistemaOrigem": "http://www.licitacaobarrinha.com.br",
                        "orgaoEntidade": {
                            "cnpj": "45.370.087/0001-27",
                            "razaoSocial": "MUNICIPIO DE BARRINHA",
                        },
                        "unidadeOrgao": {
                            "ufSigla": "SP",
                            "municipioNome": "Barrinha",
                        },
                    },
                    {
                        "numeroControlePNCP": "64614449000122-1-000626/2025",
                        "numeroCompra": "2",
                        "processo": "10/2025",
                        "objetoCompra": "CREDENCIAMENTO DE EMPRESAS PARA O FORNECIMENTO DE MEDICAMENTOS.",
                        "dataEncerramentoProposta": "2099-03-21T23:59:59",
                        "modalidadeNome": "Credenciamento",
                        "situacaoCompraNome": "Suspensa",
                    },
                ],
                "totalPaginas": 1,
            },
        }
        ,
        config=config,
    )

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    data = item.scraped_data

    assert item.url == "https://pncp.gov.br/app/editais/45370087000127/2026/8"
    assert data.title == "Pregão - Eletrônico 002 - CONTRATAÇÃO DE LEILOEIRO PÚBLICO PARA REALIZAÇÃO DE LEILÃO."
    assert data.price == 5.0
    assert data.state == "SP"
    assert data.city == "Barrinha"
    assert data.links == ["http://www.licitacaobarrinha.com.br"]
    assert data.attributes["agency_name"] == "MUNICIPIO DE BARRINHA"
    assert data.attributes["agency_tax_id"] == "45370087000127"
    assert data.attributes["portal_name"] == "PNCP"
    assert data.attributes["source_record_id"] == "45370087000127-1-000008/2026"
    assert data.attributes["process_number"] == "003"
    assert data.attributes["notice_number"] == "002"
    assert data.attributes["modality"] == "PREGAO_ELETRONICO"
    assert data.attributes["status"] == "ABERTA"
    assert data.attributes["publication_date"] == "2026-03-01"
    assert data.attributes["estimated_value"] == 5.0
    assert data.attributes["estimated_value_band"] == "ate_100k"
    assert data.attributes["mode_dispute"] == "Aberto"
    assert data.attributes["instrument_type"] == "Edital"
    assert data.attributes["amparo_legal"] == "Lei 14.133/2021"
    assert data.attributes["srp"] is True
    assert data.attributes["budget_confidential"] is False
    assert data.attributes["budget_source_count"] == 2
    assert data.attributes["proposal_url"] == "http://www.licitacaobarrinha.com.br"
    assert data.attributes["proposal_link_type"] == "sistema_origem"
    assert data.attributes["actionable_now"] is True
    assert data.attributes["buyer_type"] == "prefeitura"
    assert data.attributes["region_priority"] == "low"
    assert isinstance(data.attributes["closing_window_days"], int)
    assert data.attributes["closing_window_days"] > 0
    assert data.attributes["dedupe_key"] == "pncp:45370087000127-1-000008/2026"
    assert data.attributes["software_focus"] is False
    assert data.attributes["software_fit_score"] == 0
    assert "technology_keywords" not in data.attributes


def test_pncp_licitacoes_scrape_url_parses_detail_endpoint() -> None:
    detail_path = "/v1/orgaos/45370087000127/compras/2026/8"
    scraper = _TestPNCPLicitacoesScraper(
        {
            detail_path: {
                "numeroControlePNCP": "45370087000127-1-000008/2026",
                "numeroCompra": "002",
                "processo": "003",
                "objetoCompra": "CONTRATAÇÃO DE LEILOEIRO PÚBLICO PARA REALIZAÇÃO DE LEILÃO.",
                "valorTotalEstimado": 5.0,
                "dataPublicacaoPncp": "2026-03-01T23:52:10",
                "dataAberturaProposta": "2026-03-01T23:49:00",
                "dataEncerramentoProposta": "2099-03-12T09:00:00",
                "modalidadeNome": "Pregão - Eletrônico",
                "situacaoCompraNome": "Divulgada no PNCP",
                "modoDisputaNome": "Aberto",
                "tipoInstrumentoConvocatorioNome": "Edital",
                "amparoLegal": "Lei 14.133/2021",
                "srp": False,
                "linkSistemaOrigem": "http://www.licitacaobarrinha.com.br",
                "linkProcessoEletronico": "https://pncp.exemplo.gov.br/processo/8",
                "orgaoEntidade": {
                    "cnpj": "45370087000127",
                    "razaoSocial": "MUNICIPIO DE BARRINHA",
                },
                "unidadeOrgao": {
                    "ufSigla": "SP",
                    "municipioNome": "Barrinha",
                },
            },
        }
    )

    item = scraper.scrape_url("https://pncp.gov.br/app/editais/45370087000127/2026/8")

    assert item is not None
    assert item.scraped_data.attributes["source_record_id"] == "45370087000127-1-000008/2026"
    assert item.scraped_data.attributes["dedupe_key"] == "pncp:45370087000127-1-000008/2026"
    assert item.scraped_data.attributes["proposal_url"] == "https://pncp.exemplo.gov.br/processo/8"
    assert item.scraped_data.attributes["proposal_link_type"] == "processo_eletronico"
    assert item.scraped_data.attributes["actionable_now"] is True
    assert item.scraped_data.links == [
        "https://pncp.exemplo.gov.br/processo/8",
        "http://www.licitacaobarrinha.com.br",
    ]


def test_pncp_licitacoes_scraper_marks_software_focus_from_object_text() -> None:
    config = PNCPLicitacoesScraper.get_default_config()
    config.extra_config = {
        "target_ufs": [],
        "target_municipios_ibge": [],
    }
    scraper = _TestPNCPLicitacoesScraper(
        {
            "/v1/contratacoes/proposta?pagina=1": {
                "data": [
                    {
                        "numeroControlePNCP": "12345678000190-1-000111/2026",
                        "numeroCompra": "111",
                        "processo": "PROC-111",
                        "objetoCompra": "LICENCIAMENTO DE SOFTWARE E SUSTENTAÇÃO DE SISTEMAS CORPORATIVOS.",
                        "valorTotalEstimado": 150000.0,
                        "dataPublicacaoPncp": "2026-03-01T23:52:10",
                        "dataAberturaProposta": "2026-03-01T23:49:00",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Pregão - Eletrônico",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "orgaoEntidade": {
                            "cnpj": "12.345.678/0001-90",
                            "razaoSocial": "MUNICIPIO TESTE",
                        },
                        "unidadeOrgao": {
                            "ufSigla": "DF",
                            "municipioNome": "Brasília",
                        },
                    },
                ],
                "totalPaginas": 1,
            },
        },
        config=config,
    )

    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert data.attributes["software_focus"] is True
    assert set(data.attributes["technology_keywords"]) >= {
        "software",
        "licenciamento de software",
        "sustentacao de sistemas",
    }


def test_pncp_licitacoes_scrape_url_persists_complementary_info_for_software_item() -> None:
    detail_path = "/v1/orgaos/12345678000190/compras/2026/111"
    scraper = _TestPNCPLicitacoesScraper(
        {
            detail_path: {
                "numeroControlePNCP": "12345678000190-1-000111/2026",
                "numeroCompra": "111",
                "processo": "PROC-111",
                "objetoCompra": "CONTRATAÇÃO DE PLATAFORMA DIGITAL PARA GESTÃO DE PROCESSOS.",
                "informacaoComplementar": "Inclui aplicativo web, integrações via API e banco de dados dedicado.",
                "criterioJulgamentoNome": "Menor preço por item",
                "valorTotalEstimado": 150000.0,
                "dataPublicacaoPncp": "2026-03-01T23:52:10",
                "dataAberturaProposta": "2026-03-01T23:49:00",
                "dataEncerramentoProposta": "2099-03-12T09:00:00",
                "modalidadeNome": "Pregão - Eletrônico",
                "situacaoCompraNome": "Divulgada no PNCP",
                "orgaoEntidade": {
                    "cnpj": "12345678000190",
                    "razaoSocial": "MUNICIPIO TESTE",
                },
                "unidadeOrgao": {
                    "ufSigla": "DF",
                    "municipioNome": "Brasília",
                },
            },
        }
    )

    item = scraper.scrape_url("https://pncp.gov.br/app/editais/12345678000190/2026/111")

    assert item is not None
    assert item.scraped_data.attributes["complementary_info"] == "Inclui aplicativo web, integrações via API e banco de dados dedicado."
    assert item.scraped_data.attributes["judgment_criterion"] == "Menor preço por item"
    assert item.scraped_data.attributes["software_focus"] is True
    assert set(item.scraped_data.attributes["technology_keywords"]) >= {
        "plataforma digital",
        "aplicativo",
        "api",
        "banco de dados",
    }
    assert item.scraped_data.attributes["software_fit_score"] == 100
    assert item.scraped_data.attributes["software_subtype"] == "mixed_ti"
    assert item.scraped_data.attributes["delivery_model_hint"] == "implantacao"
    assert "Informações complementares:" in item.scraped_data.description


def test_pncp_licitacoes_scraper_avoids_false_positive_for_hardware_noise() -> None:
    config = PNCPLicitacoesScraper.get_default_config()
    config.extra_config = {
        "target_ufs": [],
        "target_municipios_ibge": [],
    }
    scraper = _TestPNCPLicitacoesScraper(
        {
            "/v1/contratacoes/proposta?pagina=1": {
                "data": [
                    {
                        "numeroControlePNCP": "12345678000190-1-000222/2026",
                        "numeroCompra": "222",
                        "processo": "PROC-222",
                        "objetoCompra": "AQUISIÇÃO DE SOFTWARE PARA IMPRESSORAS E CARTUCHOS.",
                        "valorTotalEstimado": 90000.0,
                        "dataPublicacaoPncp": "2026-03-01T23:52:10",
                        "dataAberturaProposta": "2026-03-01T23:49:00",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Pregão - Eletrônico",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "unidadeOrgao": {
                            "ufSigla": "GO",
                            "municipioNome": "Goiânia",
                        },
                    },
                ],
                "totalPaginas": 1,
            },
        },
        config=config,
    )

    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert data.attributes["software_focus"] is False
    assert "technology_keywords" not in data.attributes
    assert "software_subtype" not in data.attributes
    assert "delivery_model_hint" not in data.attributes


def test_pncp_licitacoes_scrape_url_ignores_expired_tender() -> None:
    detail_path = "/v1/orgaos/45370087000127/compras/2026/8"
    scraper = _TestPNCPLicitacoesScraper(
        {
            detail_path: {
                "numeroControlePNCP": "45370087000127-1-000008/2026",
                "numeroCompra": "002",
                "objetoCompra": "Objeto expirado",
                "dataEncerramentoProposta": "2024-03-12T09:00:00",
                "modalidadeNome": "Pregão - Eletrônico",
                "situacaoCompraNome": "Divulgada no PNCP",
            },
        }
    )

    item = scraper.scrape_url("https://pncp.gov.br/app/editais/45370087000127/2026/8")

    assert item is None


def test_pncp_licitacoes_scrape_url_keeps_legacy_control_number_url_compatibility() -> None:
    detail_path = "/v1/orgaos/45370087000127/compras/2026/8"
    scraper = _TestPNCPLicitacoesScraper(
        {
            detail_path: {
                "numeroControlePNCP": "45370087000127-1-000008/2026",
                "numeroCompra": "002",
                "objetoCompra": "Objeto legado",
                "dataEncerramentoProposta": "2099-03-12T09:00:00",
                "modalidadeNome": "Pregão - Eletrônico",
                "situacaoCompraNome": "Divulgada no PNCP",
            },
        }
    )

    item = scraper.scrape_url("https://pncp.gov.br/app/editais/45370087000127-1-000008/2026")

    assert item is not None
    assert item.scraped_data.attributes["source_record_id"] == "45370087000127-1-000008/2026"


def test_pncp_licitacoes_scrape_url_marks_missing_item() -> None:
    scraper = _TestPNCPLicitacoesScraper({})

    item = scraper.scrape_url("https://pncp.gov.br/app/editais/45370087000127-1-000008/2026")

    assert item is None
    assert scraper.last_scrape_url_diagnostics["missing"] is True


def test_pncp_licitacoes_default_config_has_initial_target_ufs() -> None:
    config = PNCPLicitacoesScraper.get_default_config()

    assert config.extra_config["target_ufs"] == ["DF", "GO", "MG", "BA", "ES", "PR", "TO"]
    assert config.extra_config["target_municipios_ibge"] == []
    assert config.extra_config["listing_start_date"] == "20240101"
    assert config.extra_config["listing_end_date"] == "20991231"
    assert config.max_items_per_run == 20000


def test_pncp_licitacoes_build_listing_params_uses_broad_listing_window() -> None:
    config = PNCPLicitacoesScraper.get_default_config()
    scraper = _TestPNCPLicitacoesScraper({}, config=config)

    params = scraper._build_listing_params(page=3, scope={"uf": "BA"})

    assert params == {
        "dataInicial": "20240101",
        "dataFinal": "20991231",
        "pagina": 3,
        "tamanhoPagina": 50,
        "uf": "BA",
    }


def test_pncp_licitacoes_scrape_distributes_pages_across_target_ufs_when_limited() -> None:
    def build_entry(prefix: str, index: int, uf: str, city: str) -> dict:
        return {
            "numeroControlePNCP": f"{prefix}-1-{index:06d}/2026",
            "numeroCompra": f"{index}",
            "objetoCompra": f"Objeto {uf} {index}",
            "dataEncerramentoProposta": "2099-03-12T09:00:00",
            "modalidadeNome": "Pregão - Eletrônico",
            "situacaoCompraNome": "Divulgada no PNCP",
            "unidadeOrgao": {"ufSigla": uf, "municipioNome": city},
        }

    config = PNCPLicitacoesScraper.get_default_config()
    config.max_items_per_run = 60
    config.extra_config = {
        "target_ufs": ["SP", "RJ"],
        "target_municipios_ibge": [],
        "listing_start_date": "20240101",
        "listing_end_date": "20991231",
    }

    scraper = _TestPNCPLicitacoesScraper(
        {
            "/v1/contratacoes/proposta?pagina=1&uf=SP": {
                "data": [build_entry("11111111000111", index, "SP", "São Paulo") for index in range(1, 51)],
                "totalPaginas": 2,
            },
            "/v1/contratacoes/proposta?pagina=2&uf=SP": {
                "data": [build_entry("11111111000111", index, "SP", "São Paulo") for index in range(51, 101)],
                "totalPaginas": 2,
            },
            "/v1/contratacoes/proposta?pagina=1&uf=RJ": {
                "data": [build_entry("22222222000122", index, "RJ", "Rio de Janeiro") for index in range(1, 51)],
                "totalPaginas": 1,
            },
        },
        config=config,
    )

    items = scraper.scrape()

    assert len(items) == 60
    assert any(item.scraped_data.state == "RJ" for item in items)


def test_pncp_licitacoes_supports_target_ufs_and_target_municipios_ibge() -> None:
    config = PNCPLicitacoesScraper.get_default_config()
    config.extra_config = {
        "target_ufs": ["SP", "RJ"],
        "target_municipios_ibge": ["3550308", "3304557"],
    }
    scraper = _TestPNCPLicitacoesScraper(
        {
            "/v1/contratacoes/proposta?pagina=1&uf=SP": {
                "data": [
                    {
                        "numeroControlePNCP": "11111111000111-1-000001/2026",
                        "numeroCompra": "001",
                        "objetoCompra": "Objeto SP",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Pregão - Eletrônico",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
                    },
                ],
                "totalPaginas": 1,
            },
            "/v1/contratacoes/proposta?pagina=1&uf=RJ": {
                "data": [
                    {
                        "numeroControlePNCP": "22222222000122-1-000002/2026",
                        "numeroCompra": "002",
                        "objetoCompra": "Objeto RJ",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Credenciamento",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "unidadeOrgao": {"ufSigla": "RJ", "municipioNome": "Rio de Janeiro"},
                    },
                ],
                "totalPaginas": 1,
            },
            "/v1/contratacoes/proposta?pagina=1&codigoMunicipioIbge=3550308": {
                "data": [
                    {
                        "numeroControlePNCP": "11111111000111-1-000001/2026",
                        "numeroCompra": "001",
                        "objetoCompra": "Objeto SP duplicado",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Pregão - Eletrônico",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
                    },
                ],
                "totalPaginas": 1,
            },
            "/v1/contratacoes/proposta?pagina=1&codigoMunicipioIbge=3304557": {
                "data": [
                    {
                        "numeroControlePNCP": "33333333000133-1-000003/2026",
                        "numeroCompra": "003",
                        "objetoCompra": "Objeto municipio",
                        "dataEncerramentoProposta": "2099-03-12T09:00:00",
                        "modalidadeNome": "Dispensa",
                        "situacaoCompraNome": "Divulgada no PNCP",
                        "unidadeOrgao": {"ufSigla": "RJ", "municipioNome": "Rio de Janeiro"},
                    },
                ],
                "totalPaginas": 1,
            },
        },
        config=config,
    )

    items = scraper.scrape()

    assert len(items) == 3
    assert [item.scraped_data.attributes["source_record_id"] for item in items] == [
        "11111111000111-1-000001/2026",
        "22222222000122-1-000002/2026",
        "33333333000133-1-000003/2026",
    ]

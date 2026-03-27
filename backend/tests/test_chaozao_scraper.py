import json
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.agribusiness.chaozao_scraper import ChaozaoScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestChaozaoScraper(ChaozaoScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None

    def add_api_response(self, page: int, payload: str) -> None:
        self._responses[self._build_listing_api_url(page)] = payload


def test_chaozao_scrape_uses_detail_page_data() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url = "https://www.chaozao.com.br/imovel/fazenda-em-botucatu-sao-paulo/FYZ3EG/"
    api_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "fazenda-em-botucatu-sao-paulo",
                    "code": "FYZ3EG",
                }
            ],
            "totalPages": 1,
        }
    )

    list_html = f"""
    <html><body>
      <a href="{detail_url}">Ver imóvel</a>
      <a href="{detail_url}">+ Detalhes</a>
      <a href="{detail_url}\\">duplicado</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Fazenda em Botucatu - São Paulo</h1>
      <span>Cabeceira</span><span>Venda</span>
      <h2>Descrição</h2>
      <p>MAGNÍFICA FAZENDA À VENDA NA REGIÃO DE BOTUCATU - SP.</p>
      <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"RealEstateListing",
        "name":"Fazenda em Botucatu - São Paulo",
        "description":"EXCLUSIVIDADE DE VENDA ... BOTUCATU - SP ... Topografia: Ondulada.",
        "image":["https://cdn.exemplo.com/imagem-1.jpg","https://cdn.exemplo.com/imagem-2.jpg"],
        "offers":{"@type":"Offer","price":30000000,"priceCurrency":"BRL"},
        "floorSize":{"value":"289,2 ha"}
      }
      </script>
      <script>
        window.__DATA__ = {
          "businessType":"SALE",
          "totalArea":289.2,
          "latitude":-22.887383333333332,
          "longitude":-48.44000555555555,
          "email":"contato@chaozao.com.br",
          "telNumber":"(62) 3030-1821",
          "pictures":[
            {"url":"https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/x/b/y/o/media/p1.jpg"},
            {"url":"https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/x/b/y/o/media/p2.jpg"}
          ]
        };
      </script>
      <footer>
        <span>Comercial: (62) 3030-1821</span>
        <span>contato@chaozao.com.br</span>
      </footer>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: list_html,
            detail_url: detail_html,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 5
    scraper.add_api_response(1, api_payload)

    items = scraper.scrape()
    assert len(items) == 1

    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Fazenda em Botucatu - São Paulo"
    assert data.city == "Botucatu"
    assert data.state == "SP"
    assert data.price == 30000000.0
    assert data.contact_name == "Chãozão"
    assert data.contact_phone == "6230301821"
    assert data.contact_email == "contato@chaozao.com.br"
    assert data.location is not None
    assert data.location.latitude == -22.887383333333332
    assert data.location.longitude == -48.44000555555555
    assert "https://cdn.exemplo.com/imagem-1.jpg" in data.images
    assert "https://cdn.exemplo.com/imagem-2.jpg" in data.images
    assert "https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/x/b/y/o/media/p1.jpg" in data.images
    assert "https://objectstorage.sa-saopaulo-1.oraclecloud.com/n/x/b/y/o/media/p2.jpg" in data.images
    assert data.attributes["area_hectares"] == 289.2
    assert data.attributes["listing_type"] == "sale"
    assert data.attributes["riverbank"] is True


def test_chaozao_scrape_uses_google_maps_url_for_location_fallback() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url = "https://www.chaozao.com.br/imovel/fazenda-em-botucatu-sao-paulo/FYZ3EG/"
    api_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "fazenda-em-botucatu-sao-paulo",
                    "code": "FYZ3EG",
                }
            ],
            "totalPages": 1,
        }
    )

    list_html = f"""
    <html><body>
      <a href="{detail_url}">+ Detalhes</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Fazenda em Botucatu - São Paulo</h1>
      <span>Cabeceira</span><span>Venda</span>
      <p>EXCLUSIVIDADE DE VENDA NA REGIÃO DE BOTUCATU - SP.</p>
      <a href="https://www.google.com/maps/place/Chaozao/@-22.8873833,-48.4400055,14z">Google Maps</a>
      <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"RealEstateListing",
        "name":"Fazenda em Botucatu - São Paulo",
        "offers":{"@type":"Offer","price":30000000,"priceCurrency":"BRL"},
        "floorSize":{"value":"289,2 ha"}
      }
      </script>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: list_html,
            detail_url: detail_html,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 5
    scraper.add_api_response(1, api_payload)

    items = scraper.scrape()
    assert len(items) == 1

    data = items[0].scraped_data
    assert data.location is not None
    assert data.location.latitude == -22.8873833
    assert data.location.longitude == -48.4400055


def test_chaozao_scrape_sanitizes_noisy_login_prefix_in_title() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url = "https://www.chaozao.com.br/imovel/fazenda-em-botucatu-sao-paulo/FYZ3EG/"
    api_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "fazenda-em-botucatu-sao-paulo",
                    "code": "FYZ3EG",
                }
            ],
            "totalPages": 1,
        }
    )

    list_html = f"""
    <html><body>
      <a href="{detail_url}">+ Detalhes</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Cod.: E5I1VI Você não está logado Você precisa entrar em sua conta para favoritar um imóvel. Registrar Entrar Fazenda em Botucatu - São Paulo</h1>
      <span>Venda</span>
      <p>EXCLUSIVIDADE DE VENDA NA REGIÃO DE BOTUCATU - SP.</p>
      <script type="application/ld+json">
      {
        "@context":"https://schema.org",
        "@type":"RealEstateListing",
        "offers":{"@type":"Offer","price":30000000,"priceCurrency":"BRL"},
        "floorSize":{"value":"289,2 ha"}
      }
      </script>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: list_html,
            detail_url: detail_html,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 5
    scraper.add_api_response(1, api_payload)

    items = scraper.scrape()
    assert len(items) == 1

    data = items[0].scraped_data
    assert data.title == "Fazenda em Botucatu - São Paulo"
    assert data.city == "Botucatu"
    assert data.state == "SP"


def test_chaozao_scrape_extracts_city_state_location_and_area_from_escaped_payload() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url = "https://www.chaozao.com.br/imovel/chacara-em-cacapava-sao-paulo-com-area-de-24000-m-r-1400000-cod-gfz638/GFZ638/"
    api_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "chacara-em-cacapava-sao-paulo-com-area-de-24000-m-r-1400000-cod-gfz638",
                    "code": "GFZ638",
                }
            ],
            "totalPages": 1,
        }
    )

    list_html = f"""
    <html><body>
      <a href="{detail_url}">+ Detalhes</a>
    </body></html>
    """
    detail_html = r"""
    <html><body>
      <h1>Chácara em Caçapava - São Paulo</h1>
      <span>Venda</span>
      <p>Descrição curta.</p>
      <script>
        self.__next_f.push([1,"{\"data\":{\"code\":\"GFZ638\",\"title\":\"Chácara\",\"propertyType\":\"Chácara\",\"price\":1400000,\"area\":24000,\"areaType\":\"metros\",\"city\":\"Caçapava\",\"state\":\"São Paulo\",\"latitude\":-23.18846388888889,\"longitude\":-45.727447222222224}}"]);
      </script>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: list_html,
            detail_url: detail_html,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 5
    scraper.add_api_response(1, api_payload)

    items = scraper.scrape()
    assert len(items) == 1

    data = items[0].scraped_data
    assert data.title == "Chácara em Caçapava - São Paulo"
    assert data.city == "Caçapava"
    assert data.state == "SP"
    assert data.price == 1400000.0
    assert data.location is not None
    assert data.location.latitude == -23.18846388888889
    assert data.location.longitude == -45.727447222222224
    assert data.attributes["area_hectares"] == 2.4


def test_chaozao_scrape_extracts_city_state_and_dms_coordinates_from_escaped_payload() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url = "https://www.chaozao.com.br/imovel/fazenda-em-cruzilia-minas-gerais/9S0XP2/"
    api_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "fazenda-em-cruzilia-minas-gerais",
                    "code": "9S0XP2",
                }
            ],
            "totalPages": 1,
        }
    )

    list_html = f"""
    <html><body>
      <a href="{detail_url}">+ Detalhes</a>
    </body></html>
    """
    detail_html = r"""
    <html><body>
      <h1>Fazenda em Cruzília - Minas Gerais</h1>
      <span>Venda</span>
      <script>
        window.__DATA__ = {"price":10000000,"city":"Cruzília","state":"Minas Gerais","lat":"21° 50' 18.00 S","long":"44° 48' 29.00 O"};
      </script>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: list_html,
            detail_url: detail_html,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 5
    scraper.add_api_response(1, api_payload)

    items = scraper.scrape()
    assert len(items) == 1

    data = items[0].scraped_data
    assert data.city == "Cruzília"
    assert data.state == "MG"
    assert data.price == 10000000.0
    assert data.location is not None
    assert data.location.latitude == pytest.approx(-21.83833333333333, rel=1e-6, abs=1e-6)
    assert data.location.longitude == pytest.approx(-44.808055555555555, rel=1e-6, abs=1e-6)


def test_chaozao_scrape_url_parses_single_detail_page() -> None:
    detail_url = "https://www.chaozao.com.br/imovel/chacara-em-mairipora-sao-paulo-com-area-de-3140-m-r-780000-cod-qgojsj/QGOJSJ/"
    detail_html = r"""
    <html><body>
      <h1>Chácara em Mairiporã - São Paulo</h1>
      <span>Venda</span>
      <script>
        window.__DATA__ = {"price":780000,"area":3140,"areaType":"metros","city":"Mairiporã","state":"São Paulo"};
      </script>
      <p>Linda chácara com casa principal e área de lazer.</p>
    </body></html>
    """

    scraper = _TestChaozaoScraper(responses={detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Chácara em Mairiporã - São Paulo"
    assert item.scraped_data.city == "Mairiporã"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.price == 780000.0
    assert item.scraped_data.attributes["area_hectares"] == 0.314


def test_chaozao_scrape_collects_multiple_pages_via_listing_api() -> None:
    list_url = "https://www.chaozao.com.br/imoveis-rurais-a-venda/"
    detail_url_1 = "https://www.chaozao.com.br/imovel/fazenda-em-botucatu-sao-paulo/FYZ3EG/"
    detail_url_2 = "https://www.chaozao.com.br/imovel/fazenda-em-cruzilia-minas-gerais/9S0XP2/"
    detail_url_3 = "https://www.chaozao.com.br/imovel/chacara-em-mairipora-sao-paulo-com-area-de-3140-m-r-780000-cod-qgojsj/QGOJSJ/"

    page_1_payload = json.dumps(
        {
            "properties": [
                {"slug": "fazenda-em-botucatu-sao-paulo", "code": "FYZ3EG"},
                {"slug": "fazenda-em-cruzilia-minas-gerais", "code": "9S0XP2"},
            ],
            "totalPages": 2,
        }
    )
    page_2_payload = json.dumps(
        {
            "properties": [
                {
                    "slug": "chacara-em-mairipora-sao-paulo-com-area-de-3140-m-r-780000-cod-qgojsj",
                    "code": "QGOJSJ",
                }
            ],
            "totalPages": 2,
        }
    )

    detail_html_1 = """
    <html><body>
      <h1>Fazenda em Botucatu - São Paulo</h1>
      <span>Venda</span>
      <script>window.__DATA__ = {"price":30000000,"city":"Botucatu","state":"São Paulo","area":289.2};</script>
    </body></html>
    """
    detail_html_2 = """
    <html><body>
      <h1>Fazenda em Cruzília - Minas Gerais</h1>
      <span>Venda</span>
      <script>window.__DATA__ = {"price":10000000,"city":"Cruzília","state":"Minas Gerais","area":190};</script>
    </body></html>
    """
    detail_html_3 = """
    <html><body>
      <h1>Chácara em Mairiporã - São Paulo</h1>
      <span>Venda</span>
      <script>window.__DATA__ = {"price":780000,"city":"Mairiporã","state":"São Paulo","area":3140,"areaType":"metros"};</script>
    </body></html>
    """

    scraper = _TestChaozaoScraper(
        responses={
            list_url: "<html><body>fallback html</body></html>",
            detail_url_1: detail_html_1,
            detail_url_2: detail_html_2,
            detail_url_3: detail_html_3,
        }
    )
    scraper.config.base_url = "https://www.chaozao.com.br"
    scraper.config.endpoint = "/imoveis-rurais-a-venda/"
    scraper.config.max_items_per_run = 3
    scraper.add_api_response(1, page_1_payload)
    scraper.add_api_response(2, page_2_payload)

    items = scraper.scrape()

    assert len(items) == 3
    assert [item.scraped_data.city for item in items] == ["Botucatu", "Cruzília", "Mairiporã"]

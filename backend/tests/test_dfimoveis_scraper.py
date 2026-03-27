from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.dfimoveis_scraper import DfImoveisScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestDfImoveisScraper(DfImoveisScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


def test_dfimoveis_scraper_collects_urls_from_sale_listing_and_enriches_detail() -> None:
    list_url = "https://www.dfimoveis.com.br/venda/df/brasilia/casa"
    detail_url = "https://www.dfimoveis.com.br/imovel/casa-condominio-4-quartos-venda-jardim-botanico-brasilia-df-condominio-morada-de-deus-1267117"
    list_html = f"""
    <html><body>
      <a href="/imovel/casa-condominio-4-quartos-venda-jardim-botanico-brasilia-df-condominio-morada-de-deus-1267117">Abrir</a>
    </body></html>
    """
    detail_html = """
    <html><head>
      <meta property="og:title" content="Casa condomínio à venda com 4 quartos no Jardim Botânico, Brasília - DFimoveis.com">
      <meta property="og:description" content="Venda de Casas em Brasília - Jardim Botânico. Cód. 1267117. Condomínio Morada de Deus.">
      <meta property="og:image" content="https://img.dfimoveis.com.br/fotos/1267117/capa.jpg">
    </head><body>
      <div class="d-flex align-items-center gap-2 exibirPrecoSalao">
        <span class="body-large">R$</span><h4 class="accent-color headline-medium precoAntigoSalao"> 1.250.000</h4>
      </div>
      <div><span class="body-large">Área Útil:</span><h4 class="accent-color headline-medium"> 320,00 m&#178;</h4></div>
      <div class="imv-card">
        <h3>Descrição</h3>
        <div>Casa em condomínio com área verde, piscina e espaço gourmet.</div>
        <div>Ideal para investimento e moradia.</div>
      </div>
      <script>
        latitude = -15.9001;
        longitude = -47.8012;
      </script>
      <div class="imv-map"><h4>DF - BRASILIA - JARDIM BOTANICO - CONDOMINIO MORADA DE DEUS</h4></div>
      <div class="swiper-slide"><img src="https://img.dfimoveis.com.br/fotos/1267117/1.jpg"></div>
      <div class="swiper-slide"><img src="https://img.dfimoveis.com.br/fotos/1267117/2.jpg"></div>
      <button data-quartos="4" data-bairro="JARDIM BOTANICO" data-cidade="BRASILIA" data-uf="DF"></button>
    </body></html>
    """

    scraper = _TestDfImoveisScraper({list_url: list_html, detail_url: detail_html})
    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    data = item.scraped_data
    assert item.url == detail_url
    assert data.title == "Casa condomínio à venda com 4 quartos no Jardim Botânico, Brasília"
    assert data.price == 1250000.0
    assert data.city == "Brasilia"
    assert data.state == "DF"
    assert data.street == "Jardim Botanico - Condominio Morada De Deus"
    assert data.location.latitude == -15.9001
    assert data.location.longitude == -47.8012
    assert len(data.images) == 3
    assert "Ideal para investimento e moradia." in data.description
    assert data.attributes["listing_type"] == "sale"
    assert data.attributes["property_type"] == "casa"
    assert data.attributes["bedrooms"] == 4
    assert data.attributes["total_area_m2"] == 320.0


def test_dfimoveis_scrape_url_works_for_rescrape() -> None:
    detail_url = "https://www.dfimoveis.com.br/imovel/casa-4-quartos-venda-lago-norte-brasilia-df-shin-qi-2-1161450"
    detail_html = """
    <html><head>
      <meta property="og:title" content="Casa à venda com 5 quartos ou + no Lago Norte, Brasília - DFimoveis.com">
    </head><body>
      <span class="body-large">R$</span><h4 class="precoAntigoSalao"> 6.500.000</h4>
      <div class="imv-card"><h3>Descrição</h3><div>Residência de alto padrão com piscina e churrasqueira.</div></div>
      <div class="imv-map"><h4>DF - BRASILIA - LAGO NORTE - SHIN QI 2</h4></div>
      <script>latitude = -15.7248129; longitude = -47.8907796;</script>
      <button data-quartos="5" data-bairro="LAGO NORTE" data-cidade="BRASILIA" data-uf="DF"></button>
    </body></html>
    """

    scraper = _TestDfImoveisScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.price == 6500000.0
    assert item.scraped_data.city == "Brasilia"
    assert item.scraped_data.state == "DF"
    assert item.scraped_data.attributes["bedrooms"] == 5

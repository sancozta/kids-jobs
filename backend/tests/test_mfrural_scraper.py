from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.agribusiness.mfrural_scraper import MFRuralScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestMFRuralScraper(MFRuralScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


def test_mfrural_scrape_collects_detail_pages_from_fazendas_listing() -> None:
    list_url = "https://www.mfrural.com.br/produtos/1-7/fazendas-imoveis-rurais"
    page_2_url = "https://www.mfrural.com.br/produtos/1-7/fazendas-imoveis-rurais?pg=2"
    detail_url_1 = "https://www.mfrural.com.br/detalhe/928659/fazenda-de-dupla-aptidao-com-1-519-hectares-em-brejinho-de-nazare-to"
    detail_url_2 = "https://www.mfrural.com.br/detalhe/928593/fazenda-324ha-em-almas-to"

    list_html = f"""
    <html><body>
      <a href="{detail_url_1}">Fazenda 1</a>
      <a href="{detail_url_1}">duplicado</a>
      <a href="{page_2_url}">Próxima</a>
    </body></html>
    """
    page_2_html = f"""
    <html><body>
      <a href="{detail_url_2}">Fazenda 2</a>
    </body></html>
    """
    detail_html_1 = """
    <html><head>
      <meta property="og:title" content="Fazenda de Dupla Aptidão com 1.519 Hectares em Brejinho de Nazaré - TO" />
    </head><body>
      <h1>Fazenda de Dupla Aptidão com 1.519 Hectares em Brejinho de Nazaré - TO</h1>
      <div class="content">
        <span>Visualizações: 8</span>
        <span>Atualizado em: 09/03/2026</span>
        <div class="tipo-cidade"><p>Brejinho de Nazaré/TO</p></div>
        <div class="preco-produto__item__preco__cheio">R$ 36.000.000,00</div>
      </div>
      <img src="https://img.mfrural.com.br/api/image?url=https://s3.amazonaws.com/mfrural-produtos-us/24389-928659-83103365-fazenda.webp&width=90&height=90&mode=4" />
      <img src="https://img.mfrural.com.br/api/image?url=https://s3.amazonaws.com/mfrural-produtos-us/24389-928659-83103365-fazenda.webp&width=767&height=521&mode=4" />
      <img src="https://img.mfrural.com.br/api/image?url=https://s3.amazonaws.com/mfrural-produtos-us/24389-928659-83103366-fazenda.webp&width=767&height=521" />
      <div class="descricao">
        <h2>Descrição</h2>
        <p>Operação de Elite.</p>
        <p>Área Total: 1.519,00 Hectares.</p>
      </div>
    </body></html>
    """
    detail_html_2 = """
    <html><body>
      <h1>Fazenda 324ha em Almas - TO</h1>
      <div class="tipo-cidade"><p>Almas/TO</p></div>
      <div class="preco-produto__item__preco__cheio">R$ 1.000.000,00</div>
      <div class="descricao">
        <h2>Descrição</h2>
        <p>Área com irrigação.</p>
      </div>
    </body></html>
    """

    scraper = _TestMFRuralScraper(
        responses={
            list_url: list_html,
            page_2_url: page_2_html,
            detail_url_1: detail_html_1,
            detail_url_2: detail_html_2,
        }
    )
    scraper.config.max_items_per_run = 10

    items = scraper.scrape()

    assert len(items) == 2
    first = items[0].scraped_data
    second = items[1].scraped_data

    assert first.title == "Fazenda de Dupla Aptidão com 1.519 Hectares em Brejinho de Nazaré - TO"
    assert first.city == "Brejinho de Nazaré"
    assert first.state == "TO"
    assert first.price == 36000000.0
    assert first.attributes["area_hectares"] == 1519.0
    assert first.attributes["listing_type"] == "sale"
    assert first.images == [
        "https://img.mfrural.com.br/api/image?url=https://s3.amazonaws.com/mfrural-produtos-us/24389-928659-83103365-fazenda.webp&width=767&height=521&mode=4",
        "https://img.mfrural.com.br/api/image?url=https://s3.amazonaws.com/mfrural-produtos-us/24389-928659-83103366-fazenda.webp&width=767&height=521",
    ]

    assert second.city == "Almas"
    assert second.state == "TO"
    assert second.price == 1000000.0
    assert second.attributes["listing_type"] == "sale"
    assert second.attributes["irrigation"] is True


def test_mfrural_scrape_url_parses_single_detail_page() -> None:
    detail_url = "https://www.mfrural.com.br/detalhe/928614/fazenda-em-minas-gerais-para-pecuaria"
    detail_html = """
    <html><body>
      <h1>Fazenda em Minas Gerais para pecuária</h1>
      <div class="tipo-cidade"><p>Conceição dos Ouros/MG</p></div>
      <div class="preco-produto__item__preco__cheio">R$ 6.000.000,00</div>
      <div class="descricao">
        <h2>Descrição</h2>
        <p>Área Total: 152 Hectares.</p>
      </div>
    </body></html>
    """

    scraper = _TestMFRuralScraper(responses={detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Fazenda em Minas Gerais para pecuária"
    assert item.scraped_data.city == "Conceição dos Ouros"
    assert item.scraped_data.state == "MG"
    assert item.scraped_data.price == 6000000.0
    assert item.scraped_data.attributes["area_hectares"] == 152.0


def test_mfrural_scrape_url_prioritizes_main_price_over_values_in_description() -> None:
    detail_url = "https://www.mfrural.com.br/detalhe/930098/chacara-2-9-ha-com-renda-e-potencial-turistico-em-ernestina-rs"
    detail_html = """
    <html><body>
      <h1>Chácara 2,9 ha com Renda e Potencial Turístico em Ernestina/RS</h1>
      <div class="descricao">
        <h2>Descrição</h2>
        <div class="descricao-texto">
          <p>Parreiral de Uvas: Em plena produção, com histórico de faturamento médio de R$ 90.000,00 por safra.</p>
          <p><b>VALOR DO INVESTIMENTO:</b></p>
          <p>R$ 1.800.000,00</p>
        </div>
      </div>
      <div class="preco-produto">
        <div class="tipo-cidade"><p>Ernestina/RS</p></div>
        <div class="preco-produto__item">
          <div class="preco-produto__container">
            <div class="preco-produto__item__wrap">
              <div>
                <div class="preco-produto__item__preco__cheio__desconto">
                  <span><strong>R$ 1.800.000,00</strong></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </body></html>
    """

    scraper = _TestMFRuralScraper(responses={detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.city == "Ernestina"
    assert item.scraped_data.state == "RS"
    assert item.scraped_data.price == 1800000.0

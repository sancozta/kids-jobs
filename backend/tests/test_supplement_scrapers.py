from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.supplements.lascolonias_scraper import LasColoniasScraper


def test_lascolonias_extracts_product_urls() -> None:
    scraper = LasColoniasScraper()
    html = """
    <html>
      <body>
        <a href="produto/whey-zero-lactose-nutrata">Item 1</a>
        <a href="/produto/w100-whey-nutrata">Item 2</a>
        <a href="/fornecedores">Fornecedor</a>
      </body>
    </html>
    """

    urls = scraper._extract_product_urls(html)

    assert urls == [
        "https://www.lascolonias.com.br/produto/whey-zero-lactose-nutrata",
        "https://www.lascolonias.com.br/produto/w100-whey-nutrata",
    ]


def test_lascolonias_parses_product_page() -> None:
    scraper = LasColoniasScraper()
    html = """
    <html>
      <head>
        <title>Whey Zero Lactose Nutrata</title>
        <meta name="description" content="Whey Zero Lactose Nutrata com preço de fábrica para lojas, academias e farmácias." />
      </head>
      <body>
        <div id="top-produtos"><h1 class="product-h1">Whey Zero Lactose</h1></div>
        <div id="img-descriptions">
          <div class="getProduct">
            <img src="midia/img/371/1714141401.png" alt="Whey Zero Lactose Nutrata" />
            <img src="midia/img/371/1714141408.png" alt="Whey Zero Lactose Nutrata" />
          </div>
          <div class="descs">
            <strong>Whey Zero Lactose</strong>
            <h2 class="factory-title">Marca: Nutrata</h2>
            <h3 class="category-title">Categoria: Hiper protéicos</h3>
            <div class="row">
              <div class="col-md-6">
                <h5>SABORES</h5>
                Baunilha<br>Chocolate<br>Morango<br>
              </div>
              <div class="col-md-6">
                <h5>EMBALAGENS</h5>
                900g<br>
              </div>
            </div>
            <div id="text-descriptions">
              <p>O Whey Zero Lactose é um suplemento com alto teor proteico por dose.</p>
              <p>É ideal para intolerantes à lactose.</p>
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    item = scraper._parse_product_page("https://www.lascolonias.com.br/produto/whey-zero-lactose-nutrata", html)

    assert item is not None
    payload = item.scraped_data.to_dict()
    assert payload["title"] == "Whey Zero Lactose"
    assert payload["images"] == [
        "https://www.lascolonias.com.br/midia/img/371/1714141401.png",
        "https://www.lascolonias.com.br/midia/img/371/1714141408.png",
    ]
    assert "Sabores: Baunilha, Chocolate, Morango" in payload["description"]
    assert payload["attributes"]["product_type"] == "po"
    assert payload["attributes"]["package_size"] == "900g"

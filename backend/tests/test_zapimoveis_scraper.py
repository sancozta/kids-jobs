from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.zapimoveis_scraper import ZapImoveisScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestZapImoveisScraper(ZapImoveisScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


def test_zapimoveis_scraper_collects_listing_urls_and_enriches_detail() -> None:
    list_url = "https://www.zapimoveis.com.br/venda/casas/rs%2Bporto-alegre/"
    detail_url = "https://www.zapimoveis.com.br/imovel/venda-casa-5-quartos-com-piscina-santo-antonio-porto-alegre-rs-280m2-id-2753069331"
    list_html = f"""
    <html><body>
      <a href="https://www.zapimoveis.com.br/imovel/venda-apartamento-centro-porto-alegre-rs-80m2-id-1/">Apto</a>
      <a href="{detail_url}/?source=ranking">Casa</a>
    </body></html>
    """
    detail_html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Imóvel em Santo Antônio, Porto Alegre - RS",
        "description": "Casa residencial para venda no bairro Santo Antônio, em Porto Alegre. Veja outros imóveis no site da Auxiliadora Predial. Fale com nossos consultores e agende uma visita agora!",
        "image": [
          "https://resizedimgs.zapimoveis.com.br/img/vr-listing/abc/{description}.webp?action={action}&dimension={width}x{height}",
          "https://resizedimgs.zapimoveis.com.br/img/vr-listing/def/{description}.webp?action={action}&dimension={width}x{height}"
        ],
        "offers": {
          "@type": "Offer",
          "priceCurrency": "BRL",
          "price": 990000
        }
      }
      </script>
    </head><body>
      <h1>Casa com 5 Quartos à venda, 280m² - Santo Antônio</h1>
      <script>
      self.__next_f.push([1,"3a:[\\"$\\",\\"$L3b\\",null,{\\"baseData\\":{\\"pageData\\":{\\"videos\\":[{\\"url\\":\\"https://www.youtube.com/watch?v=teste\\",\\"type\\":\\"VIDEO\\"}],\\"address\\":{\\"zipCode\\":\\"90660330\\",\\"city\\":\\"Porto Alegre\\",\\"streetNumber\\":\\"51\\",\\"stateAcronym\\":\\"RS\\",\\"point\\":{\\"lon\\":-51.197573,\\"lat\\":-30.061159},\\"street\\":\\"Rua Marquês de Abrantes\\",\\"neighborhood\\":\\"Santo Antônio\\"},\\"listing\\":{\\"prices\\":{\\"iptu\\":97,\\"mainValue\\":990000,\\"condominium\\":1},\\"amenities\\":[\\"POOL\\",\\"BARBECUE_GRILL\\"],\\"title\\":\\"Casa com 5 Quartos à venda, 280m²\\",\\"href\\":\\"https://www.zapimoveis.com.br/imovel/venda-casa-5-quartos-com-piscina-santo-antonio-porto-alegre-rs-280m2-id-2753069331/\\",\\"address\\":{\\"city\\":\\"Porto Alegre\\",\\"stateAcronym\\":\\"RS\\",\\"neighborhood\\":\\"Santo Antônio\\",\\"streetNumber\\":\\"51\\",\\"street\\":\\"Rua Marquês de Abrantes\\",\\"point\\":{\\"lat\\":-30.061159,\\"lon\\":-51.197573}},\\"imageList\\":[{\\"dangerousSrc\\":\\"https://resizedimgs.zapimoveis.com.br/img/vr-listing/ghi/{description}.webp?action={action}&dimension={width}x{height}\\"}],\\"unitTypes\\":[\\"HOME\\"]},\\"mainAmenities\\":{\\"usableAreas\\":\\"280 m²\\",\\"bedrooms\\":\\"5\\",\\"bathrooms\\":\\"5\\",\\"parkingSpaces\\":\\"3\\"},\\"metaContent\\":{\\"title\\":\\"Casa com 5 quartos e com piscina, 280 m² em Santo Antônio, Porto Alegre - ZAP Imóveis\\"}}}}]\n"]);
      </script>
    </body></html>
    """

    scraper = _TestZapImoveisScraper({list_url: list_html, detail_url: detail_html})
    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    data = item.scraped_data
    assert item.url == detail_url
    assert data.title == "Casa com 5 Quartos à venda, 280m² - Santo Antônio"
    assert data.description == "Casa residencial para venda no bairro Santo Antônio, em Porto Alegre."
    assert data.price == 990000.0
    assert data.currency == "BRL"
    assert data.city == "Porto Alegre"
    assert data.state == "RS"
    assert data.zip_code == "90660330"
    assert data.street == "Rua Marquês de Abrantes, 51 - Santo Antônio"
    assert data.location.latitude == -30.061159
    assert data.location.longitude == -51.197573
    assert data.images[0] == "https://resizedimgs.zapimoveis.com.br/img/vr-listing/abc/imagem.webp?action=fit-in&dimension=1024x768"
    assert data.videos == ["https://www.youtube.com/watch?v=teste"]
    assert data.attributes["listing_type"] == "sale"
    assert data.attributes["property_type"] == "casa"
    assert data.attributes["bedrooms"] == 5
    assert data.attributes["bathrooms"] == 5
    assert data.attributes["parking_spots"] == 3
    assert data.attributes["total_area_m2"] == 280.0


def test_zapimoveis_scrape_url_supports_rescrape() -> None:
    detail_url = "https://www.zapimoveis.com.br/imovel/venda-casa-3-quartos-porto-alegre-rs-180m2-id-1234567890"
    detail_html = """
    <html><head>
      <script type="application/ld+json">
      {"@context":"https://schema.org/","@type":"Product","description":"Casa espaçosa no bairro Tristeza.","offers":{"priceCurrency":"BRL","price":650000},"image":[]}
      </script>
    </head><body>
      <h1>Casa com 3 Quartos à venda, 180m² - Tristeza</h1>
      <script>
      self.__next_f.push([1,"3a:[\\"$\\",\\"$L3b\\",null,{\\"baseData\\":{\\"pageData\\":{\\"address\\":{\\"city\\":\\"Porto Alegre\\",\\"stateAcronym\\":\\"RS\\",\\"street\\":\\"Rua Exemplo\\",\\"neighborhood\\":\\"Tristeza\\"},\\"listing\\":{\\"prices\\":{\\"mainValue\\":650000},\\"unitTypes\\":[\\"HOME\\"]},\\"mainAmenities\\":{\\"usableAreas\\":\\"180 m²\\",\\"bedrooms\\":\\"3\\",\\"bathrooms\\":\\"2\\",\\"parkingSpaces\\":\\"2\\"}}}}]\n"]);
      </script>
    </body></html>
    """

    scraper = _TestZapImoveisScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.price == 650000.0
    assert item.scraped_data.city == "Porto Alegre"
    assert item.scraped_data.state == "RS"
    assert item.scraped_data.attributes["bedrooms"] == 3

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.quintoandar_scraper import QuintoAndarScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestQuintoAndarScraper(QuintoAndarScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


def test_quintoandar_scraper_collects_listing_urls_and_enriches_from_detail() -> None:
    list_url = "https://www.quintoandar.com.br/comprar/imovel/porto-alegre-rs-brasil/casa"
    detail_url = "https://www.quintoandar.com.br/imovel/893828170/comprar/casa-3-quartos-partenon-porto-alegre"
    list_html = f"""
    <html><body>
      <script>
        window.__STATE__ = {{
          "cards": [
            {{"url":"{detail_url}"}},
            {{"url":"{detail_url}"}}
          ]
        }};
      </script>
    </body></html>
    """
    detail_html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "initialState": {
              "house": {
                "houseInfo": {
                  "id": "893828170",
                  "bedrooms": 3,
                  "bathrooms": 2,
                  "parkingSpaces": 5,
                  "area": 344,
                  "type": "Casa",
                  "salePrice": 955000,
                  "iptu": 213,
                  "condoPrice": 0,
                  "acceptsPets": true,
                  "hasFurniture": false,
                  "remarks": "Excelente casa com 3 dormitórios e pátio arborizado.",
                  "generatedDescription": {
                    "longDescription": "Casa espaçosa em Porto Alegre com varanda gourmet."
                  },
                  "address": {
                    "street": "Rua Pedro Velho",
                    "neighborhood": "Partenon",
                    "city": "Porto Alegre",
                    "zipCode": "90680-510",
                    "stateAcronym": "RS",
                    "lat": -30.0670298,
                    "lng": -51.1937046
                  },
                  "amenities": [
                    {"text": "Varanda gourmet", "value": "SIM"},
                    {"text": "Quintal", "value": "SIM"},
                    {"text": "Piscina privativa", "value": "NAO"}
                  ],
                  "photos": [
                    {"url": "893828170-320.3197364718898DSC0028XXx.jpg", "cover": true},
                    {"url": "893828170-797.4734773872406DSC0031XXx.jpg", "cover": false}
                  ]
                }
              }
            }
          }
        }
      }
      </script>
    </body></html>
    """

    scraper = _TestQuintoAndarScraper({list_url: list_html, detail_url: detail_html})
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Casa com 3 quartos à venda em Partenon, Porto Alegre"
    assert data.price == 955000.0
    assert data.city == "Porto Alegre"
    assert data.state == "RS"
    assert data.street == "Rua Pedro Velho - Partenon"
    assert data.zip_code == "90680-510"
    assert data.location.latitude == -30.0670298
    assert data.location.longitude == -51.1937046
    assert "Casa espaçosa em Porto Alegre" in data.description
    assert "Excelente casa com 3 dormitórios" in data.description
    assert data.attributes["listing_type"] == "sale"
    assert data.attributes["property_type"] == "casa"
    assert data.attributes["bedrooms"] == 3
    assert data.attributes["bathrooms"] == 2
    assert data.attributes["parking_spots"] == 5
    assert data.attributes["total_area_m2"] == 344.0
    assert len(data.images) == 2


def test_quintoandar_scrape_url_supports_rescrape() -> None:
    detail_url = "https://www.quintoandar.com.br/imovel/895262363/comprar/casa-3-quartos-cavalhada-porto-alegre"
    detail_html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "initialState": {
              "house": {
                "houseInfo": {
                  "bedrooms": 3,
                  "bathrooms": 3,
                  "parkingSpaces": 2,
                  "area": 180,
                  "type": "Casa",
                  "salePrice": 780000,
                  "generatedDescription": {
                    "longDescription": "Casa com bom espaço interno e excelente potencial de valorização."
                  },
                  "address": {
                    "street": "Rua Exemplo",
                    "neighborhood": "Cavalhada",
                    "city": "Porto Alegre",
                    "zipCode": "91740-000",
                    "stateAcronym": "RS"
                  },
                  "photos": []
                }
              }
            }
          }
        }
      }
      </script>
    </body></html>
    """
    scraper = _TestQuintoAndarScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Casa com 3 quartos à venda em Cavalhada, Porto Alegre"
    assert item.scraped_data.price == 780000.0
    assert item.scraped_data.city == "Porto Alegre"
    assert item.scraped_data.state == "RS"
    assert item.scraped_data.description == "Casa com bom espaço interno e excelente potencial de valorização."


def test_quintoandar_falls_back_to_visible_description_when_payload_is_empty() -> None:
    detail_url = "https://www.quintoandar.com.br/imovel/895102953/comprar/casa-3-quartos-hipica-porto-alegre"
    detail_html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "initialState": {
              "house": {
                "houseInfo": {
                  "bedrooms": 3,
                  "bathrooms": 2,
                  "parkingSpaces": 2,
                  "area": 95,
                  "type": "Casa",
                  "salePrice": 360000,
                  "generatedDescription": {},
                  "remarks": "",
                  "address": {
                    "street": "Rua Elaine Juchem Selistre",
                    "neighborhood": "Hípica",
                    "city": "Porto Alegre",
                    "zipCode": "91787-000",
                    "stateAcronym": "RS"
                  },
                  "photos": []
                }
              }
            }
          }
        }
      }
      </script>
      <div>Sem mobília</div>
      <div>Imóvel 2402953</div>
      <div>Publicado há 4 meses</div>
      <div>Imóvel aconchegante à venda com 3 quartos e 2 banheiros no total. O imóvel fica localizado em Rua Elaine Juchem Selistre no bairro</div>
      <div>Hípica</div>
      <div>em</div>
      <div>Porto Alegre</div>
      <div>.</div>
      <div>Itens disponíveis</div>
      <div>Armários no quarto</div>
    </body></html>
    """

    scraper = _TestQuintoAndarScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.description == (
        "Imóvel aconchegante à venda com 3 quartos e 2 banheiros no total. "
        "O imóvel fica localizado em Rua Elaine Juchem Selistre no bairro Hípica em Porto Alegre."
    )

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.loft_scraper import LoftScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _TestLoftScraper(LoftScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


def test_loft_scraper_collects_house_urls_and_enriches_from_detail() -> None:
    list_url = "https://www.loft.com.br/venda/imoveis/rs/porto-alegre"
    detail_url = "https://www.loft.com.br/imovel/casa-rua-humberto-de-campos-partenon-porto-alegre-3-quartos-179m2/1vuvgdx"
    list_html = f"""
    <html><body>
      <a href="/imovel/apartamento-rua-exemplo-centro-porto-alegre-2-quartos-80m2/abc123?tipoTransacao=venda">Apartamento</a>
      <a href="/imovel/casa-rua-humberto-de-campos-partenon-porto-alegre-3-quartos-179m2/1vuvgdx?tipoTransacao=venda">Casa</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "dehydratedState": {
              "queries": [
                {
                  "queryKey": ["Sales:GetRealState", "1vuvgdx"],
                  "state": {
                    "data": {
                      "id": "1vuvgdx",
                      "price": 1450000,
                      "description": "Casa ampla&nbsp;com área gourmet e excelente potencial.<br>Vista aberta.",
                      "bedrooms": 3,
                      "restrooms": 4,
                      "parkingSpots": 2,
                      "area": 179,
                      "floor": null,
                      "complexFee": 850,
                      "propertyTax": 220,
                      "homeType": "house",
                      "image": "cover.jpg",
                      "photos": [
                        {"filename": "cover.jpg"},
                        {"filename": "garden.jpg"}
                      ],
                      "address": {
                        "streetName": "Rua Humberto de Campos",
                        "neighborhood": "Partenon",
                        "city": "Porto Alegre",
                        "state": "RS",
                        "postalCode": "90680-000",
                        "lat": -30.0670,
                        "lng": -51.1937
                      }
                    }
                  }
                }
              ]
            }
          }
        }
      }
      </script>
    </body></html>
    """

    scraper = _TestLoftScraper({list_url: list_html, detail_url: detail_html})
    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    data = item.scraped_data
    assert item.url == detail_url
    assert data.title == "Casa com 3 quartos à venda em Partenon, Porto Alegre"
    assert data.description == "Casa ampla com área gourmet e excelente potencial. Vista aberta."
    assert data.price == 1450000.0
    assert data.city == "Porto Alegre"
    assert data.state == "RS"
    assert data.zip_code == "90680-000"
    assert data.street == "Rua Humberto de Campos - Partenon"
    assert data.location.latitude == -30.067
    assert data.location.longitude == -51.1937
    assert data.images == [
        "https://content.loft.com.br/homes/1vuvgdx/cover.jpg",
        "https://content.loft.com.br/homes/1vuvgdx/garden.jpg",
    ]
    assert data.attributes["listing_type"] == "sale"
    assert data.attributes["property_type"] == "casa"
    assert data.attributes["bedrooms"] == 3
    assert data.attributes["bathrooms"] == 4
    assert data.attributes["parking_spots"] == 2
    assert data.attributes["total_area_m2"] == 179.0


def test_loft_scrape_url_supports_rescrape() -> None:
    detail_url = "https://www.loft.com.br/imovel/casa-rua-exemplo-cavalhada-porto-alegre-4-quartos-240m2/xyz987"
    detail_html = """
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {
        "props": {
          "pageProps": {
            "dehydratedState": {
              "queries": [
                {
                  "queryKey": ["Sales:GetRealState", "xyz987"],
                  "state": {
                    "data": {
                      "id": "xyz987",
                      "price": 980000,
                      "description": "Casa com pátio privativo e suíte master.",
                      "bedrooms": 4,
                      "restrooms": 3,
                      "parkingSpots": 3,
                      "area": 240,
                      "homeType": "house",
                      "photos": [],
                      "address": {
                        "streetName": "Rua Exemplo",
                        "neighborhood": "Cavalhada",
                        "city": "Porto Alegre",
                        "state": "RS"
                      }
                    }
                  }
                }
              ]
            }
          }
        }
      }
      </script>
    </body></html>
    """

    scraper = _TestLoftScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Casa com 4 quartos à venda em Cavalhada, Porto Alegre"
    assert item.scraped_data.price == 980000.0
    assert item.scraped_data.city == "Porto Alegre"
    assert item.scraped_data.state == "RS"
    assert item.scraped_data.attributes["bedrooms"] == 4

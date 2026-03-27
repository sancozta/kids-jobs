from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.imovelweb_scraper import ImovelWebScraper


class _TestImovelWebScraper(ImovelWebScraper):
    def __init__(self, listing_urls=None, details=None):
        super().__init__()
        self._listing_urls = listing_urls or []
        self._details = details or {}

    def _collect_listing_urls_with_playwright(self, url: str):  # type: ignore[override]
        return self._listing_urls

    def _extract_detail_payload_with_playwright(self, url: str):  # type: ignore[override]
        return self._details.get(url)


def test_imovelweb_scraper_collects_listing_urls_and_enriches_from_detail() -> None:
    detail_url = "https://www.imovelweb.com.br/propriedades/casa-de-4-quartos-em-vicente-pires-condominio-3028296626.html"
    detail_payload = {
        "final_url": detail_url + "?n_src=Listado&n_pos=1",
        "page_title": "Casa à venda com 4 Quartos, Vicente Pires, Vicente Pires - R$ 1.250.000, 400 m2 - ID: 3028296626 - Imovelweb",
        "title": "Casa de 4 Quartos em Vicente Pires - Condomínio Fechado",
        "article_text": """
        Casa · 280m² · 4 quartos · 2 vagas
        venda R$ 1.250.000
        Condomínio R$ 300 · IPTU R$ 10
        400 m² tot.
        280 m² útil
        3 banheiros
        2 vagas
        4 quartos
        2 suítes
        2 anos
        Casa de 4 Quartos em Vicente Pires - Condomínio Fechado
        Investimento: R$ 1.250.000,00
        Aceita permuta por apartamento de até R$ 600.000,00
        Localização: Rua 06, Vicente Pires-DF.
        O imóvel está localizado em uma das regiões mais procuradas de Vicente Pires.
        Metragem: Lote de 400m²
        Área construída de 280m².
        Imóvel: Casa com excelente distribuição e amplo espaço interno.
        Características: 4 quartos, sendo 2 suítes
        Atendimento: (61) 9 Ver dados
        Ler descrição completa
        """,
        "publisher": "Raquel Passos - Corretora de Imóveis",
        "images": [
            "https://imgbr.imovelwebcdn.com/avisos/2/30/28/29/66/26/720x532/6107255117.jpg",
            "https://imgbr.imovelwebcdn.com/avisos/2/30/28/29/66/26/720x532/6107255118.jpg",
        ],
        "ldjson_scripts": [
            """
            {
              "@context": "https://schema.org",
              "@type": "House",
              "name": "Casa à venda com 4 Quartos, Vicente Pires, Vicente Pires - R$ 1.250.000, 400 m2 - ID: 3028296626 - Imovelweb",
              "description": "Investimento: R$ 1.250.000,00 Aceita permuta por apartamento de até R$ 600.000,00 Localização: Rua 06, Vicente Pires-DF.",
              "image": "https://imgbr.imovelwebcdn.com/avisos/2/30/28/29/66/26/720x532/6107255117.jpg",
              "numberOfBathroomsTotal": 3,
              "numberOfBedrooms": 4,
              "telephone": "55 61998185056"
            }
            """
        ],
    }

    scraper = _TestImovelWebScraper([detail_url, detail_url], {detail_url: detail_payload})
    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.url == detail_url
    assert item.scraped_data.title == "Casa de 4 Quartos em Vicente Pires - Condomínio Fechado"
    assert item.scraped_data.price == 1250000.0
    assert item.scraped_data.city == "Vicente Pires"
    assert item.scraped_data.state == "DF"
    assert item.scraped_data.street == "Rua 06, Vicente Pires-DF"
    assert item.scraped_data.contact_name == "Raquel Passos - Corretora de Imóveis"
    assert item.scraped_data.contact_phone == "61998185056"
    assert "Aceita permuta" in (item.scraped_data.description or "")
    assert item.scraped_data.attributes["property_type"] == "casa"
    assert item.scraped_data.attributes["total_area_m2"] == 400.0
    assert item.scraped_data.attributes["bedrooms"] == 4
    assert item.scraped_data.attributes["bathrooms"] == 3
    assert item.scraped_data.attributes["parking_spots"] == 2
    assert len(item.scraped_data.images) == 2


def test_imovelweb_scrape_url_supports_rescrape() -> None:
    detail_url = "https://www.imovelweb.com.br/propriedades/kitnet-studio-no-sudoeste!-eqrsw-2-3-com-1-quarto.-3028870154.html"
    detail_payload = {
        "final_url": detail_url + "?n_src=Listado&n_pos=3",
        "page_title": "Apartamento à venda com 1 Quarto, Sudoeste, Brasília - R$ 439.000, 27 m2 - ID: 3028870154 - Imovelweb",
        "title": "Kitnet Studio no Sudoeste! EQRSW 2/3 com 1 quarto.",
        "article_text": """
        Apartamento · 27m² · 1 quarto
        venda R$ 439.000
        Condomínio R$ 557
        27 m² tot.
        1 quarto
        1 banheiro
        Kitnet Studio no Sudoeste! EQRSW 2/3 com 1 quarto.
        Localização: Quadra EQRSW 2/3, Sudoeste-DF.
        Imóvel compacto e reformado.
        Ler descrição completa
        """,
        "publisher": "Imobiliária Exemplo",
        "images": [],
        "ldjson_scripts": [
            """
            {
              "@context": "https://schema.org",
              "@type": "Apartment",
              "name": "Apartamento à venda com 1 Quarto, Sudoeste, Brasília - R$ 439.000, 27 m2 - ID: 3028870154 - Imovelweb",
              "telephone": "55 6133332222"
            }
            """
        ],
    }

    scraper = _TestImovelWebScraper(details={detail_url: detail_payload})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.url == detail_url
    assert item.scraped_data.price == 439000.0
    assert item.scraped_data.city == "Brasília"
    assert item.scraped_data.state == "DF"
    assert item.scraped_data.street == "Quadra EQRSW 2/3, Sudoeste-DF"
    assert item.scraped_data.contact_phone == "6133332222"

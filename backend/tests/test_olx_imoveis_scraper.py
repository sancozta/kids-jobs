from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.properties.olx_imoveis_scraper import OLXImoveisScraper


def test_olx_imoveis_extracts_listing_urls() -> None:
    scraper = OLXImoveisScraper()
    html = """
    <a href="https://df.olx.com.br/distrito-federal-e-regiao/imoveis/casa-a-venda-1234567890">Item 1</a>
    <a href="https://df.olx.com.br/distrito-federal-e-regiao/imoveis/casa-em-condominio-1234567891">Item 2</a>
    """
    urls = scraper._extract_listing_urls(html)
    assert urls == [
        "https://df.olx.com.br/distrito-federal-e-regiao/imoveis/casa-a-venda-1234567890",
        "https://df.olx.com.br/distrito-federal-e-regiao/imoveis/casa-em-condominio-1234567891",
    ]


def test_olx_imoveis_parses_detail_page() -> None:
    scraper = OLXImoveisScraper()
    html = """
    <html>
      <head>
        <title>Casa em condominio fechado 4 quartos à venda - Nova Colina (Sobradinho), Brasília - DF 1484414244 | OLX</title>
      </head>
      <body>
        <div>Casa 4 quartos Condomínio recanto da serra</div>
        <div>
          O refúgio perfeito para sua família no Recanto da Serra!
          Espaço de sobra e lazer completo.
          Ver descrição completa
        </div>
        <div>Localização</div>
        <div>Condomínio Recanto da Serra Rua 3</div>
        <div>Nova Colina (Sobradinho), Brasília, DF, 73270359</div>
        <div>Detalhes</div>
        <div>Área construída</div><div>500m²</div>
        <div>Quartos</div><div>4</div>
        <div>Banheiros</div><div>4</div>
        <div>Vagas na garagem</div><div>2</div>
        <div>Características do imóvel</div>
        <div>Área de serviço</div>
        <div>Churrasqueira</div>
        <div>Características do condomínio</div>
        <div>Condomínio fechado</div>
        <div>Segurança 24h</div>
        <div>PROFISSIONAL</div>
        <div>Almir Escritório Imobiliário</div>
        <div>Último acesso há 31 min</div>
        <div>R$ 670.000</div>
        <div>Condomínio</div><div>R$ 500 / mês</div>
        <img src="https://img.olx.com.br/images/01/0123456789.jpg" />
        <img src="https://img.olx.com.br/images/02/0223456789.jpg" />
        <div>Código do anúncio: 1484414244</div>
      </body>
    </html>
    """
    item = scraper._parse_detail_page(
        "https://df.olx.com.br/distrito-federal-e-regiao/imoveis/casa-4-quartos-condominio-recanto-da-serra-1484414244",
        html,
    )
    assert item is not None
    payload = item.scraped_data.to_dict()
    assert payload["title"] == "Casa em condominio fechado 4 quartos à venda - Nova Colina (Sobradinho), Brasília - DF"
    assert payload["price"] == 670000.0
    assert payload["street"] == "Condomínio Recanto da Serra Rua 3"
    assert payload["city"] == "Brasília"
    assert payload["state"] == "DF"
    assert payload["zip_code"] == "73270-359"
    assert payload["contact_name"] == "Almir Escritório Imobiliário"
    assert payload["attributes"]["listing_type"] == "sale"
    assert payload["attributes"]["property_type"] == "casa"
    assert payload["attributes"]["bedrooms"] == 4
    assert payload["attributes"]["bathrooms"] == 4
    assert payload["attributes"]["parking_spots"] == 2
    assert payload["attributes"]["building_area_m2"] == 500.0


def test_olx_imoveis_extracts_main_price_after_long_description() -> None:
    scraper = OLXImoveisScraper()
    long_description = " ".join(["Ambiente amplo e arejado."] * 160)
    html = f"""
    <html>
      <head>
        <title>Casa em condominio fechado 3 quartos à venda - Setor Habitacional Arniqueira (Águas Claras), Brasília - DF 1466413429 | OLX</title>
      </head>
      <body>
        <div>Linda casa 3 quartos sendo 1 suite com edicula escriturada e quitada.</div>
        <div>
          {long_description}
          Taxa condominial anunciada de apenas R$ 160,00.
          Ver descrição completa
        </div>
        <div>Localização</div>
        <div>Setor Habitacional Arniqueira (Águas Claras)</div>
        <div>Brasília, DF, 71996250</div>
        <div>Detalhes</div>
        <div>Área construída</div><div>356m²</div>
        <div>Quartos</div><div>3</div>
        <div>Banheiros</div><div>3</div>
        <div>R$ 739.000</div>
        <div>Venda</div>
        <div>Condomínio</div><div>R$ 190 / mês</div>
        <div>IPTU</div><div>R$ 1.000</div>
        <div>Código do anúncio: 1466413429</div>
      </body>
    </html>
    """

    item = scraper._parse_detail_page(
        "https://df.olx.com.br/distrito-federal-e-regiao/imoveis/linda-casa-3-quartos-sendo-1-suite-com-edicula-escriturada-e-quitada-1466413429",
        html,
    )

    assert item is not None
    assert item.scraped_data.price == 739000.0

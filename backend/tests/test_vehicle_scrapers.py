import json

from adapters.outbound.scraping.implementations.vehicles.icarros_scraper import ICarrosScraper
from adapters.outbound.scraping.implementations.vehicles.kavak_scraper import KavakScraper
from adapters.outbound.scraping.implementations.vehicles.mobiauto_scraper import MobiAutoScraper
from adapters.outbound.scraping.implementations.vehicles.olx_vehicles_scraper import OLXVehiclesScraper
from adapters.outbound.scraping.implementations.vehicles.webmotors_scraper import WebMotorsScraper


def test_vehicle_scrapers_are_disabled_by_default() -> None:
    assert ICarrosScraper.get_default_config().enabled is False
    assert KavakScraper.get_default_config().enabled is False
    assert MobiAutoScraper.get_default_config().enabled is False
    assert OLXVehiclesScraper.get_default_config().enabled is False
    assert WebMotorsScraper.get_default_config().enabled is False


def test_icarros_parses_vehicle_ld_json_detail() -> None:
    scraper = ICarrosScraper()
    item = scraper._parse_detail_page(
        "https://www.icarros.com.br/comprar/angra-dos-reis-rj/peugeot/307/2011/d46786187",
        """
        <html><head>
          <meta name="description" content="Peugeot 307 à venda em Angra dos Reis - RJ">
          <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Vehicle",
            "name": "Peugeot 307",
            "brand": {"@type": "Brand", "name": "Peugeot"},
            "model": "307",
            "vehicleModelDate": "2010",
            "mileageFromOdometer": {"@type": "QuantitativeValue", "value": "120000", "unitText": "KM"},
            "fuelType": "Flex",
            "vehicleTransmission": "manual",
            "bodyType": "Hatch",
            "color": "Prata",
            "image": [{"@type": "ImageObject", "contentUrl": "https://img/1.jpg"}],
            "offers": {"@type": "Offer", "price": "21500", "priceCurrency": "BRL"}
          }
          </script>
        </head><body></body></html>
        """,
    )
    assert item is not None
    assert item.scraped_data.title == "Peugeot 307"
    assert item.scraped_data.price == 21500.0
    assert item.scraped_data.city == "Angra Dos Reis"
    assert item.scraped_data.state == "RJ"
    assert item.scraped_data.images == ["https://img/1.jpg"]


def test_kavak_parses_car_graph_detail() -> None:
    scraper = KavakScraper()
    payload = {
        "@graph": [
            {"@type": "Organization", "name": "Kavak"},
            {
                "@type": "Car",
                "name": "Fiat Fastback 1.0 T200 MHEV AUDACE CVT Suv 2026",
                "url": "https://www.kavak.com/br/venda/fiat-fastback-10_t200_mhev_audace_cvt-suv-2026",
                "offers": {"@type": "Offer", "price": 125099, "priceCurrency": "BRL"},
                "model": "Fastback",
                "mileageFromOdometer": {"@type": "QuantitativeValue", "value": 10535, "unitCode": "KMT"},
                "vehicleConfiguration": "T200 MHEV AUDACE CVT",
                "vehicleModelDate": "2026",
                "bodyType": "Suv",
                "color": "Preto",
                "vehicleIdentificationNumber": "VIN123",
                "vehicleTransmission": "Automático",
                "image": ["https://img/1.jpg", "https://img/2.jpg"],
                "brand": {"@type": "Brand", "name": "Fiat"},
                "vehicleEngine": {"@type": "EngineSpecification", "fuelType": "Flex"},
            },
        ],
        "@context": "https://schema.org",
    }
    item = scraper._parse_detail_page(
        "https://www.kavak.com/br/venda/fiat-fastback-10_t200_mhev_audace_cvt-suv-2026",
        f"""
        <html><head>
          <meta name="description" content="Fiat Fastback seminovo na Kavak">
          <script type="application/ld+json">{json.dumps(payload)}</script>
        </head><body></body></html>
        """,
    )
    assert item is not None
    assert item.scraped_data.title == "Fiat Fastback 1.0 T200 MHEV AUDACE CVT Suv 2026"
    assert item.scraped_data.price == 125099.0
    assert item.scraped_data.images == ["https://img/1.jpg", "https://img/2.jpg"]
    assert item.scraped_data.attributes["brand"] == "Fiat"
    assert item.scraped_data.attributes["model"] == "Fastback"
    assert item.scraped_data.attributes["mileage_km"] == 10535


def test_mobiauto_parses_next_data_detail() -> None:
    scraper = MobiAutoScraper()
    payload = {
        "props": {
            "pageProps": {
                "deal": {
                    "id": 22822477,
                    "makeName": "Hyundai",
                    "modelName": "HB20",
                    "trimName": "Vision 1.0",
                    "modelYear": 2022,
                    "productionYear": 2022,
                    "price": 62900,
                    "comments": "HB20 completo",
                    "km": 168402,
                    "fuelName": "Flex",
                    "transmissionName": "Manual",
                    "bodystyleName": "Hatch",
                    "colorName": "Prata",
                    "doors": 4,
                    "dealerCity": "São José dos Campos",
                    "dealerState": "SP",
                    "dealerAddress": "Av. Perseu",
                    "dealerPhone": "12999999999",
                    "dealerLocation": "-23.2023413,-45.9096953",
                },
                "images": [
                    {"imageSrc": "https://img/1.jpg"},
                    {"imageSrc": "https://img/2.jpg"},
                ],
            }
        }
    }
    item = scraper._parse_detail_page(
        "https://www.mobiauto.com.br/comprar/carros/sp-sao-jose-dos-campos/hyundai/hb20/2022/vision-1-0/detalhes/22822477",
        f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>',
    )
    assert item is not None
    assert item.scraped_data.title == "Hyundai HB20 2022 Vision 1.0"
    assert item.scraped_data.price == 62900.0
    assert item.scraped_data.city == "São José Dos Campos"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.location.latitude == -23.2023413


def test_webmotors_parses_detail_page() -> None:
    scraper = WebMotorsScraper()
    item = scraper._parse_detail_page(
        "https://www.webmotors.com.br/comprar/toyota/corolla-cross/18-vvt-i-hybrid-flex-xrx-cvt/4-portas/2021-2022/66549928",
        """
        <html>
          <head><title>TOYOTA COROLLA CROSS 1.8 VVT-I HYBRID FLEX XRX CVT - WebMotors - 66549928</title></head>
          <body>
            <h1>TOYOTA COROLLA CROSS 1.8 VVT-I HYBRID FLEX XRX CVT</h1>
            <ul>
              <li>Cidade<strong>São Paulo - SP</strong></li>
              <li>Ano<strong>2021/2022</strong></li>
              <li>KM<strong>84.941</strong></li>
              <li>Câmbio<strong>Automática</strong></li>
              <li>Carroceria<strong>Utilitário esportivo</strong></li>
              <li>Combustível<strong>Gasolina e elétrico</strong></li>
              <li>Cor<strong>Prata</strong></li>
            </ul>
            <div>R$ 136.999</div>
            <section>
              <h2>Itens de veículo</h2>
              <h3>Airbag</h3>
              <h3>Ar condicionado</h3>
              <h3>Sensor de estacionamento</h3>
            </section>
            <section><h2>Confiança e tranquilidade</h2></section>
            <img src="https://image.webmotors.com.br/abc1.jpg" />
            <img src="https://image.webmotors.com.br/abc2.jpg" />
          </body>
        </html>
        """,
    )
    assert item is not None
    assert item.scraped_data.title == "TOYOTA COROLLA CROSS 1.8 VVT-I HYBRID FLEX XRX CVT"
    assert item.scraped_data.price == 136999.0
    assert item.scraped_data.city == "São Paulo"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.images == [
        "https://image.webmotors.com.br/abc1.jpg",
        "https://image.webmotors.com.br/abc2.jpg",
    ]
    assert item.scraped_data.attributes["body_type"] == "Utilitário esportivo"
    assert item.scraped_data.attributes["features"] == [
        "Airbag",
        "Ar condicionado",
        "Sensor de estacionamento",
    ]


def test_olx_parses_detail_page() -> None:
    scraper = OLXVehiclesScraper()
    item = scraper._parse_detail_page(
        "https://df.olx.com.br/distrito-federal-e-regiao/autos-e-pecas/carros-vans-e-utilitarios/volkswagen-virtus-exclusive-250tsi-1-4-flex-16v-aut-2025-1476191052",
        """
        <html>
          <head>
            <title>Volkswagen Virtus Exclusive 250tsi 1.4 Flex 16V AUT 2025 - 1476191052 | OLX</title>
          </head>
          <body>
            Volkswagen Virtus Exclusive 250tsi 1.4 Flex 16V AUT 2025
            Virtus Exclusive 2025 com apenas 4 mil Km rodados!
            Ver descrição completa
            Histórico Veicular
            Detalhes
            Modelo
            Volkswagen Exclusive 250tsi 1.4 Flex 16v Aut
            Marca
            Volkswagen
            Tipo de veículo
            Sedã
            Ano
            2025
            Quilometragem
            4000
            Potência do motor
            1.4
            Combustível
            Flex
            Câmbio
            Automático
            Cor
            Branco
            Portas
            4 Portas
            Opcionais deste veículo
            Air bag
            Ar condicionado
            Outras Características
            Com manual
            Com garantia
            Localização
            Asa Sul
            Brasília, DF, 70384020
            R$ 138.999
            R$ 136.999
            <img src="https://img.olxcdn.com.br/images/01.jpg" />
            <img src="https://img.olxcdn.com.br/images/02.jpg" />
          </body>
        </html>
        """,
    )
    assert item is not None
    assert item.scraped_data.title == "Volkswagen Virtus Exclusive 250tsi 1.4 Flex 16V AUT 2025"
    assert item.scraped_data.description == "Virtus Exclusive 2025 com apenas 4 mil Km rodados!"
    assert item.scraped_data.price == 136999.0
    assert item.scraped_data.city == "Brasília"
    assert item.scraped_data.state == "DF"
    assert item.scraped_data.zip_code == "70384-020"
    assert item.scraped_data.images == [
        "https://img.olxcdn.com.br/images/01.jpg",
        "https://img.olxcdn.com.br/images/02.jpg",
    ]
    assert item.scraped_data.attributes["brand"] == "Volkswagen"
    assert item.scraped_data.attributes["body_type"] == "Sedã"
    assert item.scraped_data.attributes["features"] == [
        "Air bag",
        "Ar condicionado",
        "Com manual",
        "Com garantia",
    ]

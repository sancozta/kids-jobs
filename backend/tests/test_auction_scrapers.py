from adapters.outbound.scraping.implementations.auctions.copart_scraper import CopartScraper
from adapters.outbound.scraping.implementations.auctions.megaleiloes_scraper import MegaLeiloesScraper
from adapters.outbound.scraping.implementations.auctions.portalzuk_scraper import PortalZukScraper
from adapters.outbound.scraping.implementations.auctions.sodresantoro_scraper import SodreSantoroScraper
from adapters.outbound.scraping.implementations.auctions.superbid_scraper import SuperBidScraper


def test_copart_normalizes_detail_and_photo_urls() -> None:
    assert CopartScraper.get_default_config().enabled is False
    assert CopartScraper._normalize_listing_url("https://www.copart.com.br/lot/1002130/Photos") == "https://www.copart.com.br/lot/1002130"
    assert CopartScraper._normalize_listing_url("https://www.copart.com.br/lot/1002130") == "https://www.copart.com.br/lot/1002130"
    assert CopartScraper._normalize_listing_url("https://www.copart.com.br/lot/") == ""


def test_copart_listing_uses_standardized_auction_attributes() -> None:
    scraper = CopartScraper()
    soup = scraper.parse_html(
        """
        <div>
          <a href="https://www.copart.com.br/lot/1002130/Photos">TOYOTA COROLLA XEI</a>
          R$ 45.000,00 São Paulo - SP
        </div>
        """
    )
    item = scraper._parse_listing(soup.select_one("a"))
    assert item is not None
    assert item.scraped_data.attributes["listing_type"] == "direct_sale"
    assert item.scraped_data.attributes["lot_number"] == "1002130"
    assert item.scraped_data.attributes["auction_code"] == "1002130"
    assert item.scraped_data.attributes["asset_type"] == "veiculo"
    assert item.scraped_data.attributes["auctioneer"] == "Copart Brasil"


def test_portalzuk_extracts_canonical_listing_urls() -> None:
    scraper = PortalZukScraper()
    soup = scraper.parse_html(
        """
        <html><body>
          <a href="/imovel/sp/sao-paulo/bela-vista/avenida-paulista-1374/35626-221907">ok</a>
          <a href="/imovel/sp/sao-paulo/bela-vista/avenida-paulista-1374/35626-221907?utm=x">dup</a>
          <a href="/leilao-de-imoveis/tl/proximos-leiloes">ignore</a>
        </body></html>
        """
    )
    assert scraper._extract_listing_urls(soup) == [
        "https://www.portalzuk.com.br/imovel/sp/sao-paulo/bela-vista/avenida-paulista-1374/35626-221907"
    ]


def test_portalzuk_parses_detail_page() -> None:
    scraper = PortalZukScraper()
    item = scraper._parse_detail_page(
        "https://www.portalzuk.com.br/imovel/sp/sao-paulo/bela-vista/avenida-paulista-1374/35626-221907",
        """
        <html><head>
          <meta property="og:title" content="Imóvel a venda - Imóvel Comercial - Bela Vista - São Paulo/SP cod: 221907 | Zuk">
          <meta property="og:image" content="https://imagens.portalzuk.com.br/detalhe/1.jpg">
        </head><body>
          <div class="property-info"><h3 class="property-info-title">Descrição do imóvel</h3><div class="property-info-text">Descrição principal</div></div>
          <div class="property-info"><h3 class="property-info-title">Observações</h3><div class="property-info-text">Observações finais</div></div>
          <div class="property-gallery-image"><img src="https://imagens.portalzuk.com.br/detalhe/2.jpg"></div>
          <li class="card-property-price">
            <span class="card-property-price-label">Valor</span>
            <span class="card-property-price-value">R$ 215.000,00</span>
          </li>
          <li class="card-property-price">
            <span class="card-property-price-label">1º leilão</span>
            <span class="card-property-price-value">R$ 329.722,52</span>
          </li>
          <span class="form-help">Mínimo: R$ 58.275,00</span>
        </body></html>
        """,
    )
    assert item is not None
    assert item.scraped_data.city == "Sao Paulo"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.price == 215000.0
    assert "Descrição principal" in item.scraped_data.description
    assert len(item.scraped_data.images) == 2
    assert item.scraped_data.attributes["auction_id"] == "35626"
    assert item.scraped_data.attributes["lot_number"] == "221907"
    assert item.scraped_data.attributes["auction_code"] == "35626-221907"
    assert item.scraped_data.attributes["appraisal_value"] == 329722.52
    assert item.scraped_data.attributes["minimum_bid"] == 58275.0
    assert item.scraped_data.attributes["discount_pct"] == 34.79
    assert item.scraped_data.attributes["auctioneer"] == "Portal Zuk"


def test_portalzuk_filters_non_residential_assets() -> None:
    scraper = PortalZukScraper()
    item = scraper._parse_detail_page(
        "https://www.portalzuk.com.br/imovel/sp/sao-paulo/bela-vista/avenida-paulista-1374/35626-221907",
        """
        <html><head>
          <meta property="og:title" content="Leilão de Prédio Comercial - Bela Vista - São Paulo/SP cod: 221907 | Zuk">
        </head><body>
          <li class="card-property-price"><span class="card-property-price-label">Valor</span><span class="card-property-price-value">R$ 215.000,00</span></li>
        </body></html>
        """,
    )
    assert item is None


def test_sodresantoro_parses_listing_card() -> None:
    scraper = SodreSantoroScraper()
    soup = scraper.parse_html(
        """
        <a href="https://leilao.sodresantoro.com.br/leilao/28176/lote/2724938/">
          <img src="https://img/1.jpg" alt="Imagem 1 do casa (desocupado) - centro - leme - sp">
          Leilão 28176 - 001 12387 casa (desocupado) - centro - leme - sp Dione Marinelli e outros
          12/03/26 11:00 2 dias Lance inicial (R$) 630.000,00 casa leme / SP
        </a>
        """
    )
    item = scraper._parse_listing(soup.select_one("a"))
    assert item is not None
    assert item.scraped_data.title == "casa (desocupado) - centro - leme - sp"
    assert item.scraped_data.price == 630000.0
    assert item.scraped_data.attributes["auction_id"] == "28176"
    assert item.scraped_data.attributes["lot_number"] == "001"
    assert item.scraped_data.attributes["auction_code"] == "12387"
    assert item.scraped_data.attributes["auction_date"] == "2026-03-12"
    assert item.scraped_data.attributes["auction_start_at"] == "2026-03-12T11:00:00"
    assert item.scraped_data.attributes["auctioneer"] == "Sodré Santoro"
    assert item.scraped_data.attributes["asset_type"] == "casa"


def test_megaleiloes_parses_detail_page() -> None:
    scraper = MegaLeiloesScraper()
    item = scraper._parse_detail_page(
        "https://www.megaleiloes.com.br/imoveis/casas/rj/marica/casa-384-m2-condominio-residencial-terras-alphaville-marica-2-marica-rj-x120964",
        """
        <html><head>
          <title>Casa 384 m² - Condomínio Residencial Terras Alphaville Maricá 2 - Maricá - RJ | Mega Leilões</title>
          <meta property="og:image" content="https://cdn1.megaleiloes.com.br/batches/120964/cover.jpg">
        </head><body>
          <div id="tab-description"><div class="content">Descrição detalhada do lote.</div></div>
          <img data-mfp-src="https://cdn1.megaleiloes.com.br/batches/120964/1.jpg">
          1ª Praça: 12/03/2026 às 15:00 R$ 2.006.000,00
          2ª Praça: 19/03/2026 às 15:00 R$ 1.543.876,48
        </body></html>
        """,
    )
    assert item is not None
    assert item.scraped_data.state == "RJ"
    assert item.scraped_data.city == "Marica"
    assert item.scraped_data.price == 2006000.0
    assert item.scraped_data.attributes["auction_code"] == "120964"
    assert item.scraped_data.attributes["lot_number"] == "120964"
    assert item.scraped_data.attributes["auction_date"] == "2026-03-12"
    assert item.scraped_data.attributes["appraisal_value"] == 2006000.0
    assert item.scraped_data.attributes["minimum_bid"] == 1543876.48
    assert item.scraped_data.attributes["discount_pct"] == 23.04
    assert item.scraped_data.attributes["auctioneer"] == "Mega Leilões"


def test_megaleiloes_filters_non_target_property() -> None:
    scraper = MegaLeiloesScraper()
    item = scraper._parse_detail_page(
        "https://www.megaleiloes.com.br/imoveis/comerciais/sp/sao-paulo/sala-comercial-x120964",
        """
        <html><head><title>Sala Comercial - São Paulo - SP | Mega Leilões</title></head>
        <body><div id="tab-description"><div class="content">Descrição.</div></div></body></html>
        """,
    )
    assert item is None


def test_megaleiloes_filters_commercial_property() -> None:
    scraper = MegaLeiloesScraper()
    item = scraper._parse_detail_page(
        "https://www.megaleiloes.com.br/imoveis/comerciais/sp/campinas/imovel-comercial-j120964",
        """
        <html><head><title>Imóvel Comercial no Centro - Campinas/SP | Mega Leilões</title></head>
        <body><div id="tab-description"><div class="content">Descrição.</div></div></body></html>
        """,
    )
    assert item is None


def test_superbid_parses_next_data_detail_page() -> None:
    scraper = SuperBidScraper()
    item = scraper._parse_detail_page(
        "https://www.superbid.net/oferta/casa-com-area-de-6960m2-mogi-das-cruzes-4521906",
        """
        <html><head><meta property="og:image" content="https://ms.sbwebservices.net/photos/a.jpg"></head><body>
          <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "offerDetails": {
                  "offers": [{
                    "lotNumber": "11",
                    "price": 116000,
                    "endDateTime": "2026-03-10T15:00:00",
                    "offerStatus": {"desc": "Aberto"},
                    "offerDescription": {"offerDescription": "<p>Descrição da oferta</p>"},
                    "auction": {
                      "id": 684,
                      "currencyIso": "BRL",
                      "beginDate": "2026-03-10T12:00:00",
                      "address": {"streetType": "Rua", "street": "Dos Remédios", "number": "156", "city": "São Paulo", "stateCode": "SP"}
                    },
                    "product": {
                      "shortDesc": "CASA COM AREA DE 69,60M2 - MOGI DAS CRUZES",
                      "detailedDescription": "<p>Detalhes completos</p>",
                      "galleryJson": [{"link": "https://ms.sbwebservices.net/photos/1.jpg"}],
                      "location": {"city": "Mogi das Cruzes - SP", "state": "São Paulo", "locationGeo": {"lat": -23.53, "lon": -46.17}},
                      "productType": {"description": "Casa"}
                    },
                    "seller": {"name": "Hasta Pública"},
                    "store": {"name": "Zaccarino Leilões"}
                  }]
                },
                "eventDetails": {"events": []}
              }
            }
          }
          </script>
        </body></html>
        """,
    )
    assert item is not None
    assert item.scraped_data.title == "CASA COM AREA DE 69,60M2 - MOGI DAS CRUZES"
    assert item.scraped_data.price == 116000
    assert item.scraped_data.city == "Mogi das Cruzes"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.attributes["auction_id"] == "684"
    assert item.scraped_data.attributes["lot_number"] == "11"
    assert item.scraped_data.attributes["auction_code"] == "684-11"
    assert item.scraped_data.attributes["auction_date"] == "2026-03-10"
    assert item.scraped_data.attributes["auctioneer"] == "Zaccarino Leilões"
    assert item.scraped_data.location.latitude == -23.53


def test_superbid_filters_non_target_property() -> None:
    scraper = SuperBidScraper()
    item = scraper._parse_detail_page(
        "https://www.superbid.net/oferta/sala-consultorio-123",
        """
        <html><body>
          <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "offerDetails": {
                  "offers": [{
                    "lotNumber": "1",
                    "price": 95000,
                    "auction": {"id": 684, "currencyIso": "BRL"},
                    "product": {
                      "shortDesc": "SALA/CONSULTÓRIO 87.97 m2, BELO HORIZONTE / MG",
                      "location": {"city": "Belo Horizonte - MG", "state": "Minas Gerais"},
                      "productType": {"description": "Sala Comercial"}
                    }
                  }]
                },
                "eventDetails": {"events": []}
              }
            }
          }
          </script>
        </body></html>
        """,
    )
    assert item is None

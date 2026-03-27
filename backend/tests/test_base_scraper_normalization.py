from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.base_scraper import BaseScraper


def test_normalize_scraped_data_extracts_city_state_from_location_raw_without_persisting_raw() -> None:
    payload = {
        "title": "Casa ampla",
        "location": {"raw": "Campinas - SP"},
        "attributes": {"source_platform": "test", "listing_type": "sale"},
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="properties")

    assert normalized.city == "Campinas"
    assert normalized.state == "SP"
    assert "location_raw" not in normalized.attributes
    assert "raw_location" not in normalized.attributes
    assert normalized.attributes == {"listing_type": "sale"}


def test_normalize_scraped_data_uses_raw_location_attribute_fallback_and_drops_it() -> None:
    payload = {
        "attributes": {
            "source_platform": "test",
            "raw_location": "Brasilia/DF",
            "company": "Empresa X",
            "salary_text": "R$ 3.000 - R$ 5.000",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="jobs")

    assert normalized.city == "Brasilia"
    assert normalized.state == "DF"
    assert "raw_location" not in normalized.attributes
    assert normalized.attributes == {
        "company": "Empresa X",
        "salary_range": 3000.0,
    }


def test_normalize_scraped_data_preserves_existing_city_state_and_uppercases_uf() -> None:
    payload = {
        "city": "Niteroi",
        "state": "rj",
        "location": {"raw": "Sao Paulo - SP"},
        "attributes": {"source_platform": "test"},
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="properties")

    assert normalized.city == "Niteroi"
    assert normalized.state == "RJ"


def test_normalize_scraped_data_normalizes_state_name_to_uf() -> None:
    payload = {
        "city": "Belo Horizonte",
        "state": "Minas Gerais",
        "attributes": {"source_platform": "test"},
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="properties")

    assert normalized.city == "Belo Horizonte"
    assert normalized.state == "MG"


def test_normalize_scraped_data_strips_html_from_description() -> None:
    payload = {
        "title": "Fazenda em Cruzilia - Minas Gerais",
        "description": "<p>Texto <strong>principal</strong></p><ul><li>Item 1</li><li>Item 2&nbsp;</li></ul>",
        "attributes": {"listing_type": "sale"},
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="agribusiness")

    assert normalized.description == "Texto principal Item 1 Item 2"


def test_normalize_scraped_data_removes_question_marks_from_description() -> None:
    payload = {
        "description": "Primeiro bloco? Segundo bloco??",
        "attributes": {"company": "Empresa X"},
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="jobs")

    assert normalized.description == "Primeiro bloco Segundo bloco"


def test_normalize_scraped_data_standardizes_vehicle_attributes() -> None:
    payload = {
        "attributes": {
            "source_platform": "webmotors",
            "mileage": "80.000 km",
            "year": "2019/2020",
            "brand": "Honda",
            "model": "Civic",
            "version": "EXL",
            "fuel_type": "Híbrido",
            "doors": "4 portas",
            "color": "Prata",
            "engine": "2.0",
            "transmission": "Automático",
            "raw_location": "Sao Paulo/SP",
            "category_slug": "nao_deve_entrar",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="vehicles")

    assert normalized.attributes == {
        "mileage_km": 80000,
        "year": 2019,
        "brand": "Honda",
        "model": "Civic",
        "version": "EXL",
        "fuel_type": "hibrido",
        "doors": 4,
        "color": "Prata",
        "engine": "2.0",
        "transmission": "automatica",
    }


def test_normalize_scraped_data_replaces_properties_area_m2_with_total_area_m2() -> None:
    payload = {
        "attributes": {
            "listing_type": "rent",
            "property_type": "Apartamento",
            "bedrooms": "3",
            "bathrooms": "2",
            "parking_spots": "1",
            "floor": "8º",
            "area_m2": "95,5 m2",
            "building_area_m2": "88 m2",
            "property_tax": "R$ 100",  # removido da taxonomia
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="properties")

    assert normalized.attributes == {
        "listing_type": "rent",
        "property_type": "apartamento",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spots": 1,
        "floor": 8,
        "total_area_m2": 95.5,
        "building_area_m2": 88.0,
    }


def test_normalize_scraped_data_standardizes_jobs_contract_and_work_model() -> None:
    payload = {
        "attributes": {
            "company": "Empresa Y",
            "salary_range": "R$ 7.000 a R$ 9.000",
            "seniority": "Sênior",
            "contract_type": "CLT",
            "work_model": "Home Office",
            "experience_years": "5 anos",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="jobs")

    assert normalized.attributes == {
        "company": "Empresa Y",
        "salary_range": 7000.0,
        "seniority": "senior",
        "contract_type": "clt",
        "work_model": "remoto",
        "experience_years": 5,
    }


def test_normalize_scraped_data_extracts_salary_type_and_backfills_price_for_jobs() -> None:
    payload = {
        "price": None,
        "attributes": {
            "company": "Empresa Z",
            "salary_range": "$150,000 up to $200,000 USD/Annual",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="jobs")

    assert normalized.price == 150000.0
    assert normalized.attributes == {
        "company": "Empresa Z",
        "salary_range": 150000.0,
        "salary_type": "anual",
    }


def test_normalize_scraped_data_drops_non_numeric_salary_range() -> None:
    payload = {
        "attributes": {
            "company": "Empresa W",
            "salary_range": "Salário a Combinar",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="jobs")

    assert normalized.attributes == {"company": "Empresa W"}


def test_normalize_scraped_data_standardizes_auctions_and_removes_category_slug() -> None:
    payload = {
        "attributes": {
            "listing_type": "Leilão",
            "auction_id": "684",
            "lot": "11",
            "auction_code": "L-123",
            "auction_date": "09/03/26 10:00",
            "auction_status": "Aberto para lances",
            "auction_start_at": "2026-03-09 10:00:00",
            "auction_end_at": "2026-03-10 18:30",
            "asset_type": "Imóvel residencial",
            "appraisal_value": "R$ 500.000,00",
            "minimum_bid": "R$ 350.000,00",
            "current_bid": "R$ 420.000,00",
            "auctioneer": "Leilões XPTO",
            "category_slug": "deve-sair",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="auctions")

    assert normalized.attributes == {
        "listing_type": "auction",
        "auction_id": "684",
        "lot_number": "11",
        "auction_code": "L-123",
        "auction_date": "2026-03-09",
        "auction_status": "aberto",
        "auction_start_at": "2026-03-09T10:00:00",
        "auction_end_at": "2026-03-10T18:30:00",
        "asset_type": "Imóvel residencial",
        "appraisal_value": 500000.0,
        "minimum_bid": 350000.0,
        "current_bid": 420000.0,
        "auctioneer": "Leilões XPTO",
    }


def test_normalize_scraped_data_standardizes_agribusiness_and_removes_category_slug() -> None:
    payload = {
        "attributes": {
            "listing_type": "catalog",
            "area_hectares": "128,7 ha",
            "offer_count": "12 ofertas",
            "auction_date": "2026-03-09",
            "riverbank": "sim",
            "irrigation": "não",
            "category_slug": "deve-sair",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="agribusiness")

    assert normalized.attributes == {
        "listing_type": "catalog",
        "area_hectares": 128.7,
        "offer_count": 12,
        "auction_date": "2026-03-09",
        "riverbank": True,
        "irrigation": False,
    }


def test_normalize_scraped_data_standardizes_supplements_schema() -> None:
    payload = {
        "attributes": {
            "listing_type": "institutional",  # removido da taxonomia
            "supplier_count": "20",
            "product_type": "Cápsula",
            "package_size": "60 cápsulas",
            "concentration": "500mg",
            "certifications": "ANVISA; ISO 9001; GMP",
            "white_label": "true",
        }
    }

    normalized = BaseScraper._normalize_scraped_data(payload, category="supplements")

    assert normalized.attributes == {
        "supplier_count": 20,
        "product_type": "capsula",
        "package_size": "60 cápsulas",
        "concentration": "500mg",
        "certifications": ["ANVISA", "ISO 9001", "GMP"],
        "white_label": True,
    }


def test_extract_coordinates_from_google_maps_text_parses_at_pattern() -> None:
    text = "https://www.google.com/maps/place/Fazenda/@-22.8873833,-48.4400055,14z"
    latitude, longitude = BaseScraper.extract_coordinates_from_google_maps_text(text)

    assert latitude == -22.8873833
    assert longitude == -48.4400055


def test_extract_coordinates_from_google_maps_text_parses_query_pattern() -> None:
    text = 'href="https:\\/\\/www.google.com\\/maps?q=loc:-15.794229,-47.882166\\u0026z=16"'
    latitude, longitude = BaseScraper.extract_coordinates_from_google_maps_text(text)

    assert latitude == -15.794229
    assert longitude == -47.882166

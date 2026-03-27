from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.jobs.telegram_jobs_ti_scraper import TelegramJobsTIScraper


class _FakeEntity:
    def __init__(self, chat_id: int, title: str, username: str | None = None):
        self.id = chat_id
        self.title = title
        self.username = username


class _FakeMessage:
    def __init__(self, message_id: int, text: str | None = None, *, has_photo: bool = False):
        self.id = message_id
        self.message = text
        self.text = text
        self.raw_text = text
        self.entities = []
        self.photo = object() if has_photo else None
        self.document = None
        self.date = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


class _TestTelegramJobsTIScraper(TelegramJobsTIScraper):
    def __init__(self, channel_messages: dict[str, list[tuple[_FakeEntity, _FakeMessage]]]):
        super().__init__()
        self.channel_messages = channel_messages
        self.saved_offsets: list[tuple[str, int]] = []
        self.downloaded_media = b"fake-image"

    def _telegram_channels(self) -> list[str]:
        return list(self.channel_messages.keys())

    def _ensure_client_started(self):
        self._client = object()
        return self._client

    def _shutdown_client(self) -> None:
        self._client = None

    def _iter_channel_messages(self, client, channel_ref: str):
        return list(self.channel_messages.get(channel_ref, []))

    def _save_offset(self, chat_id: str, last_message_id: int) -> None:
        self.saved_offsets.append((chat_id, last_message_id))

    def _download_message_media_bytes(self, client, message):
        return self.downloaded_media

    def _ocr_image_bytes(self, image_bytes: bytes | None):
        if image_bytes:
            return "Senior Python Developer Remote PJ"
        return None


class _ConfiguredOCRTelegramJobsTIScraper(_TestTelegramJobsTIScraper):
    def __init__(self, channel_messages: dict[str, list[tuple[_FakeEntity, _FakeMessage]]], ocr_text: str | None):
        super().__init__(channel_messages)
        self.ocr_text = ocr_text

    def _ocr_image_bytes(self, image_bytes: bytes | None):
        return self.ocr_text if image_bytes else None


def test_telegram_jobs_ti_scraper_processes_multiple_channels_and_updates_offsets() -> None:
    entity_br = _FakeEntity(1001, "Vagas TI BR", "vagasti")
    entity_world = _FakeEntity(1002, "Remote Worldwide")
    message_br = _FakeMessage(
        12,
        "Vaga: backend python senior\nEmpresa: Acme\nModelo: Remoto\nContrato: PJ\nSalário: R$ 15.000\nContato: jobs@acme.dev",
    )
    message_world = _FakeMessage(
        33,
        "Senior Software Engineer\nCompany: Globex\nRemote - Latam\nContractor\n5 years of experience",
    )

    scraper = _TestTelegramJobsTIScraper(
        {
            "@grupo_br": [(entity_br, message_br)],
            "@grupo_world": [(entity_world, message_world)],
        }
    )

    items = scraper.scrape()

    assert len(items) == 2
    first = items[0].to_dict()
    second = items[1].to_dict()

    assert first["url"] == "telegram://1001/12"
    assert first["scraped_data"]["title"] == "Backend Python Senior"
    assert first["scraped_data"]["contact_email"] == "jobs@acme.dev"
    assert first["scraped_data"]["attributes"]["company"] == "Acme"
    assert first["scraped_data"]["attributes"]["contract_type"] == "pj"
    assert first["scraped_data"]["attributes"]["work_model"] == "remoto"
    assert first["scraped_data"]["attributes"]["telegram_chat"] == "Vagas TI BR"
    assert first["scraped_data"]["attributes"]["telegram_message_id"] == 12

    assert second["scraped_data"]["attributes"]["company"] == "Globex"
    assert second["scraped_data"]["attributes"]["seniority"] == "senior"
    assert second["scraped_data"]["attributes"]["experience_years"] == 5
    assert ("1001", 12) in scraper.saved_offsets
    assert ("1002", 33) in scraper.saved_offsets


def test_telegram_jobs_ti_scraper_uses_ocr_for_image_only_posts() -> None:
    entity = _FakeEntity(2001, "Imagens de Vagas")
    message = _FakeMessage(44, None, has_photo=True)
    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})

    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["attributes"]["ocr_used"] is True
    assert payload["attributes"]["source_message_type"] == "image"
    assert payload["title"] == "Senior Python Developer PJ"


def test_telegram_jobs_ti_formats_structured_ocr_cards_and_ignores_generic_caption_noise() -> None:
    entity = _FakeEntity(2101, "Vagas Portuguesas de TI", "vagastiportugal")
    message = _FakeMessage(
        55,
        "Estamos a crescer e a recrutar ! Vem para WA Fenix! Envie seu cv: selecao@wafx.pt",
        has_photo=True,
    )
    scraper = _ConfiguredOCRTelegramJobsTIScraper(
        {"@grupo": [(entity, message)]},
        (
            "Tester Automação\n"
            "Cidade: 100% remoto\n"
            "Nível: Sênior\n"
            "Duração: 1 ano\n"
            "Requisitos:\n"
            "4+ anos de experiência;\n"
            "Conhecimentos de Java, BDD, SQL e Selenium para realização de Testes automáticos;\n"
            "Experiência com Jira e Confluence;\n"
            "Certificação ISTQB (desejável).\n"
            "OBS: Forma de atendimento 100% remoto com disponibilidade de atuação no fuso horário de Portugal"
        ),
    )

    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["title"] == "Tester Automação"
    assert payload["attributes"]["company"] == "WA Fenix"
    assert payload["contact_email"] == "selecao@wafx.pt"
    assert "Estamos a crescer" not in payload["description"]
    assert "Vem para WA Fenix" not in payload["description"]
    assert "Cidade: 100% remoto" in payload["description"]
    assert "Requisitos:" in payload["description"]
    assert "- 4+ anos de experiência" in payload["description"]
    assert "Observações:" in payload["description"]
    assert payload["attributes"]["work_model"] == "remoto"
    assert payload["attributes"]["seniority"] == "senior"


def test_telegram_jobs_ti_removes_emojis_from_title_and_description() -> None:
    entity = _FakeEntity(2201, "Vagas Portuguesas de TI", "vagastiportugal")
    message = _FakeMessage(
        56,
        "🔥 Estamos a crescer! 🚀 Envie seu cv: selecao@wafx.pt",
        has_photo=True,
    )
    scraper = _ConfiguredOCRTelegramJobsTIScraper(
        {"@grupo": [(entity, message)]},
        (
            "🔥 Tester Automação 🚀\n"
            "📍 Cidade: 100% remoto\n"
            "✅ Nível: Sênior\n"
            "📝 Requisitos:\n"
            "• Java\n"
            "• Selenium"
        ),
    )

    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["title"] == "Tester Automação"
    assert "🔥" not in payload["title"]
    assert "🚀" not in payload["title"]
    assert "📍" not in payload["description"]
    assert "✅" not in payload["description"]
    assert "📝" not in payload["description"]
    assert "•" not in payload["description"]


def test_telegram_jobs_ti_removes_asterisks_from_title_and_description() -> None:
    entity = _FakeEntity(2301, "Vagas Portuguesas de TI", "vagastiportugal")
    message = _FakeMessage(
        57,
        "*Estamos a crescer!* Envie seu cv: selecao@wafx.pt",
        has_photo=True,
    )
    scraper = _ConfiguredOCRTelegramJobsTIScraper(
        {"@grupo": [(entity, message)]},
        (
            "*Tester Automação*\n"
            "*Cidade:* 100% remoto\n"
            "*Nível:* Sênior\n"
            "*Requisitos:*\n"
            "* Java\n"
            "* Selenium"
        ),
    )

    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["title"] == "Tester Automação"
    assert "*" not in payload["title"]
    assert "*" not in payload["description"]
    assert "Cidade: 100% remoto" in payload["description"]
    assert "- Java" in payload["description"]


def test_telegram_jobs_ti_does_not_extract_company_from_fuso_horario_context() -> None:
    assert TelegramJobsTIScraper._extract_company(
        "Disponibilidade de atuação no fuso horário de Portugal",
        [],
        None,
    ) is None


def test_telegram_jobs_ti_scrape_url_fetches_single_message() -> None:
    entity = _FakeEntity(3001, "Canal Jobs", "canaljobs")
    message = _FakeMessage(88, "Vaga: frontend react pleno\nEmpresa: Orbit\nRemoto\nCLT")

    class _SingleLookupScraper(_TestTelegramJobsTIScraper):
        def _ensure_client_started(self):
            outer = self

            class _FakeLoop:
                @staticmethod
                def run_until_complete(value):
                    return value

            class _Client:
                loop = _FakeLoop()

                @staticmethod
                def is_connected():
                    return True

                @staticmethod
                def get_entity(chat_id):
                    assert chat_id == 3001
                    return entity

                @staticmethod
                def get_messages(current_entity, ids=None):
                    assert current_entity is entity
                    assert ids == 88
                    return message

            self._client = _Client()
            return self._client

    scraper = _SingleLookupScraper({})
    item = scraper.scrape_url("telegram://3001/88")

    assert item is not None
    payload = item.to_dict()["scraped_data"]
    assert payload["attributes"]["company"] == "Orbit"
    assert payload["attributes"]["contract_type"] == "clt"
    assert payload["title"] == "Frontend React Pleno"


def test_telegram_jobs_ti_scrape_url_resolves_legacy_positive_channel_id_via_configured_channel() -> None:
    entity = _FakeEntity(3001, "Canal Jobs", "canaljobs")
    message = _FakeMessage(88, "Vaga: frontend react pleno\nEmpresa: Orbit\nRemoto\nCLT")

    class _LegacyLookupScraper(_TestTelegramJobsTIScraper):
        def _telegram_channels(self) -> list[str]:
            return ["@canaljobs"]

        def _ensure_client_started(self):
            class _Client:
                @staticmethod
                def is_connected():
                    return True

                @staticmethod
                def get_entity(value):
                    if value == "@canaljobs":
                        return entity
                    raise ValueError("Could not find the input entity for PeerUser(user_id=3001)")

                @staticmethod
                def get_messages(current_entity, ids=None):
                    assert current_entity is entity
                    assert ids == 88
                    return message

            self._client = _Client()
            return self._client

    scraper = _LegacyLookupScraper({})
    item = scraper.scrape_url("telegram://3001/88")

    assert item is not None
    assert scraper.last_scrape_url_diagnostics["missing"] is False
    payload = item.to_dict()["scraped_data"]
    assert payload["attributes"]["company"] == "Orbit"
    assert payload["title"] == "Frontend React Pleno"


def test_telegram_jobs_ti_extracts_header_company_and_location() -> None:
    entity = _FakeEntity(4001, "Busque o Melhor", "busqueomelhor")
    message = _FakeMessage(
        101,
        "📢 VAGA CIENTISTA DE DADOS – RIBEIRÃO PRETO /SP – K-LAB DIGITAL 📢\nAtuação 100% remoto\nContratação PJ",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["title"] == "Cientista De Dados"
    assert payload["city"] == "Ribeirão Preto"
    assert payload["state"] == "SP"
    assert payload["attributes"]["company"] == "K-LAB DIGITAL"
    assert payload["attributes"]["dedupe_key"].startswith("text:")


def test_telegram_jobs_ti_extracts_location_with_spaced_hyphen_separator() -> None:
    entity = _FakeEntity(4501, "Vagas TI", "vagasti")
    message = _FakeMessage(
        111,
        "Vaga: Desenvolvedor Python\nLocal: São Paulo - SP\nModelo: Remoto\nContrato: CLT",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["city"] == "São Paulo"
    assert payload["state"] == "SP"


def test_telegram_jobs_ti_does_not_turn_sentence_into_city_with_hyphen_se() -> None:
    entity = _FakeEntity(4601, "Vagas TI", "vagasti")
    message = _FakeMessage(
        112,
        "Vaga: Desenvolvedor Python\nAtuação: suporte ao usuário quando solicitado comunicar-se\nModelo: Remoto\nContrato: CLT",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["city"] is None
    assert payload["state"] is None


def test_telegram_jobs_ti_skips_aggregate_posts() -> None:
    entity = _FakeEntity(5001, "Busque o Melhor", "busqueomelhor")
    message = _FakeMessage(
        202,
        "🌟 Oportunidade de Carreira na Stefanini Group! 🌟\nTemos vagas disponíveis tanto para trabalho remoto quanto presencial.\nhttps://lnkd.in/a1\nhttps://lnkd.in/a2\nhttps://lnkd.in/a3",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert items == []


def test_telegram_jobs_ti_derives_company_and_title_from_links_and_removes_emojis() -> None:
    entity = _FakeEntity(6001, "Busque o Melhor", "busqueomelhor")
    message = _FakeMessage(
        303,
        "🔥 https://vagasdeempregoce.com/analista-cqa-remoto-compass-uol-2026/\nAnalista CQA Remoto Compass UOL 2026 🚀",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert len(items) == 1
    payload = items[0].to_dict()["scraped_data"]
    assert payload["title"] == "Analista CQA"
    assert payload["attributes"]["company"] == "Compass UOL"
    assert "🔥" not in payload["description"]
    assert "🚀" not in payload["description"]


def test_telegram_jobs_ti_skips_generic_referral_posts() -> None:
    entity = _FakeEntity(7001, "Vagas TI", "vagasti")
    message = _FakeMessage(
        404,
        "https://work.vetto.ai/opportunities?referral=GTcVAn7e\nParticipe de projetos remotos, flexíveis e ganhe até R$600/h",
    )

    scraper = _TestTelegramJobsTIScraper({"@grupo": [(entity, message)]})
    items = scraper.scrape()

    assert items == []

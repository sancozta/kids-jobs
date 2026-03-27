from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.jobs.remotar_scraper import RemotarScraper
from adapters.outbound.scraping.implementations.jobs.remoteok_scraper import RemoteOKScraper
from adapters.outbound.scraping.implementations.jobs.spassu_scraper import SpassuScraper
from adapters.outbound.scraping.implementations.jobs.weworkremotely_scraper import WeWorkRemotelyScraper
from adapters.outbound.scraping.implementations.jobs.wellfound_scraper import WellfoundScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _MultiResponseMixin:
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


class _TestRemotarScraper(_MultiResponseMixin, RemotarScraper):
    pass


class _TestWeWorkRemotelyScraper(_MultiResponseMixin, WeWorkRemotelyScraper):
    pass


class _TestRemoteOKScraper(_MultiResponseMixin, RemoteOKScraper):
    pass


class _TestWellfoundScraper(_MultiResponseMixin, WellfoundScraper):
    pass


class _TestSpassuScraper(_MultiResponseMixin, SpassuScraper):
    pass


def test_remotar_scraper_parses_homepage_and_detail() -> None:
    list_html = """
    <html><body>
      <a href="/job/130267/scopic-software/remote-c++qt3d-engineer">Remote C++/QT/3D Engineer</a>
      <a href="/job/130268/non-tech-company/analista-financeiro">Analista Financeiro</a>
    </body></html>
    """
    job_payload = {
        "props": {
            "pageProps": {
                "jobData": {
                    "title": "Remote C++/QT/3D Engineer",
                    "subtitle": "Engenharia remota com foco em C++ e 3D.",
                    "description": "<p>This is a remote position.</p><p>5+ years with modern C++ and Qt.</p>",
                    "moreInfos": "<p><strong>Outras Informações</strong></p><ul><li>Contratação CLT.</li><li>Benefício de home office.</li></ul>",
                    "type": "remote",
                    "externalLink": "https://company.example/apply",
                    "company": {"name": "Scopic Software"},
                    "jobSalary": {"type": "Hourly", "value": {"minimum": 50, "maximum": 80}},
                    "country": {"name": "Brasil"},
                    "jobTags": [
                        {"tag": {"name": "🧓🏽 Sênior"}},
                        {"tag": {"name": "💼 CLT"}},
                        {"tag": {"name": "🌍 100% Remoto"}},
                    ],
                }
            }
        }
    }
    detail_url = "https://remotar.com.br/job/130267/scopic-software/remote-c++qt3d-engineer"
    scraper = _TestRemotarScraper(
        {
            "https://remotar.com.br/": list_html,
            detail_url: f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(job_payload)}</script>',
        }
    )

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.url == detail_url
    assert item.scraped_data.title == "Remote C++/QT/3D Engineer"
    assert "Outras Informações" in item.scraped_data.description
    assert "Contratação CLT." in item.scraped_data.description
    assert "Benefício de home office." in item.scraped_data.description
    assert item.scraped_data.attributes["company"] == "Scopic Software"
    assert item.scraped_data.attributes["seniority"] == "senior"
    assert item.scraped_data.attributes["contract_type"] == "clt"
    assert item.scraped_data.attributes["work_model"] == "remoto"
    assert item.scraped_data.attributes["experience_years"] == 5


def test_weworkremotely_scraper_parses_programming_rss_feed() -> None:
    rss = """
    <rss version="2.0">
      <channel>
        <item>
          <title>Lemon.io: Senior Java Full-stack Developer</title>
          <link>https://weworkremotely.com/remote-jobs/lemon-io-senior-java-full-stack-developer</link>
          <category>Full-Stack Programming</category>
          <region>Anywhere in the World</region>
          <description><![CDATA[<p>Senior Java role. 5+ years experience. Full-time.</p>]]></description>
        </item>
        <item>
          <title>ACME: Sales Manager</title>
          <link>https://weworkremotely.com/remote-jobs/acme-sales-manager</link>
          <category>Sales and Marketing</category>
          <region>Anywhere in the World</region>
          <description><![CDATA[<p>Sales role</p>]]></description>
        </item>
      </channel>
    </rss>
    """
    scraper = _TestWeWorkRemotelyScraper(
        {"https://weworkremotely.com/categories/remote-programming-jobs.rss": rss}
    )

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.scraped_data.title == "Senior Java Full-stack Developer"
    assert item.scraped_data.attributes["company"] == "Lemon.io"
    assert item.scraped_data.attributes["seniority"] == "senior"
    assert item.scraped_data.attributes["work_model"] == "remoto"


def test_remoteok_scraper_parses_json_feed() -> None:
    payload = json.dumps(
        [
            {"last_updated": 1, "legal": "terms"},
            {
                "id": "123",
                "url": "https://remoteok.com/remote-jobs/remote-senior-python-backend-engineer-123",
                "company": "Example Co",
                "position": "Senior Python Backend Engineer",
                "description": "<p>Build APIs with Python. 6+ years experience. Full-time.</p>",
                "salary_min": 120000,
                "salary_max": 180000,
                "location": "",
                "apply_url": "https://remoteok.com/remote-jobs/remote-senior-python-backend-engineer-123",
                "tags": ["python", "backend", "software"],
            },
        ]
    )
    scraper = _TestRemoteOKScraper({"https://remoteok.com/remote-dev-jobs.json": payload})

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.scraped_data.title == "Senior Python Backend Engineer"
    assert item.scraped_data.attributes["company"] == "Example Co"
    assert item.scraped_data.attributes["seniority"] == "senior"
    assert item.scraped_data.attributes["experience_years"] == 6


def test_wellfound_scraper_parses_list_and_detail_page() -> None:
    list_html = """
    <html><body>
      <a href="/jobs/3938437-software-engineer">Software Engineer</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Software Engineer</h1>
      <ul><li>$150k – $170k</li><li>Remote (Everywhere)</li><li>Full Time</li></ul>
      <h2>About the job</h2>
      <p>Build modern software products.</p>
      <p>3-5 years of professional software development experience.</p>
      <h2>About the company</h2>
      <a href="/company/remesh">Remesh</a>
    </body></html>
    """
    scraper = _TestWellfoundScraper(
        {
            "https://wellfound.com/role/r/software-engineer": list_html,
            "https://wellfound.com/jobs/3938437-software-engineer": detail_html,
        }
    )

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.scraped_data.title == "Software Engineer"
    assert item.scraped_data.attributes["company"] == "Remesh"
    assert item.scraped_data.attributes["contract_type"] == "clt"
    assert item.scraped_data.attributes["experience_years"] == 3


def test_spassu_scraper_filters_non_tech_and_parses_detail() -> None:
    list_html = """
    <html><body>
      <a href="https://spassu.zohorecruit.com/jobs/Careers/1/Desenvolvedor-Fullstack?source=CareerSite">Desenvolvedor Fullstack</a>
      <a href="https://spassu.zohorecruit.com/jobs/Careers/2/Analista-de-Documentos?source=CareerSite">Analista de Documentos</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Desenvolvedor Fullstack Sr - Python/React</h1>
      <p>spassu | Full time</p>
      <p>Trabalho remoto | Postado em 22/01/2026</p>
      <h3>Informações da vaga</h3>
      <ul>
        <li>Data da abertura 22/01/2026</li>
        <li>Tipo de emprego Full time</li>
        <li>Cidade Rio de Janeiro</li>
        <li>Estado/Província RJ</li>
        <li>País Brasil</li>
        <li>CEP/Código postal 20031-170</li>
        <li>Trabalho remoto Sim</li>
      </ul>
      <h3>Descrição da vaga</h3>
      <p>Este é um cargo remoto.</p>
      <p>Atuar no desenvolvimento de aplicações com Python, FastAPI e React.</p>
      <h3>Requisitos</h3>
      <div>3 anos de experiência com APIs REST.</div>
    </body></html>
    """
    scraper = _TestSpassuScraper(
        {
            "https://spassu.zohorecruit.com/jobs/Careers": list_html,
            "https://spassu.zohorecruit.com/jobs/Careers/1/Desenvolvedor-Fullstack?source=CareerSite": detail_html,
            "https://spassu.zohorecruit.com/jobs/Careers/2/Analista-de-Documentos?source=CareerSite": "<h1>Analista de Documentos</h1>",
        }
    )

    items = scraper.scrape()

    assert len(items) == 1
    item = items[0]
    assert item.scraped_data.title == "Desenvolvedor Fullstack Sr - Python/React"
    assert item.scraped_data.attributes["company"] == "Spassu"
    assert item.scraped_data.city == "Rio de Janeiro"
    assert item.scraped_data.state == "RJ"
    assert item.scraped_data.zip_code == "20031170"
    assert item.scraped_data.attributes["country"] == "Brasil"
    assert item.scraped_data.attributes["contract_type"] == "clt"
    assert item.scraped_data.attributes["work_model"] == "remoto"

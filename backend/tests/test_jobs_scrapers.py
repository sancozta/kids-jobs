from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.outbound.scraping.implementations.jobs.bne_scraper import BNEScraper
from adapters.outbound.scraping.implementations.jobs.catho_scraper import CathoScraper
from adapters.outbound.scraping.implementations.jobs.infojobs_scraper import InfoJobsScraper
from adapters.outbound.scraping.implementations.jobs.nerdin_scraper import NerdinScraper
from adapters.outbound.scraping.implementations.jobs.tractian_scraper import TractianScraper
from adapters.outbound.scraping.implementations.jobs.vanhack_scraper import VanHackScraper


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _SingleResponseScraperMixin:
    def __init__(self, html: str):
        super().__init__()
        self._html = html

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        return _FakeResponse(self._html)


class _TestCathoScraper(_SingleResponseScraperMixin, CathoScraper):
    pass


class _TestInfoJobsScraper(_SingleResponseScraperMixin, InfoJobsScraper):
    pass


class _TestBNEScraper(_SingleResponseScraperMixin, BNEScraper):
    pass


class _TestNerdinScraper(_SingleResponseScraperMixin, NerdinScraper):
    pass


class _TestVanHackScraper(_SingleResponseScraperMixin, VanHackScraper):
    pass


class _TestTractianScraper(TractianScraper):
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


class _MultiResponseScraperMixin:
    def __init__(self, responses: dict[str, str]):
        super().__init__()
        self._responses = responses

    def fetch_page(self, url: str, method: str = "GET", **kwargs):  # type: ignore[override]
        html = self._responses.get(url)
        return _FakeResponse(html) if html is not None else None


class _TestCathoDetailScraper(_MultiResponseScraperMixin, CathoScraper):
    pass


class _TestInfoJobsDetailScraper(_MultiResponseScraperMixin, InfoJobsScraper):
    pass


class _TestBNEDetailScraper(_MultiResponseScraperMixin, BNEScraper):
    pass


class _TestNerdinDetailScraper(_MultiResponseScraperMixin, NerdinScraper):
    pass


class _TestVanHackDetailScraper(_MultiResponseScraperMixin, VanHackScraper):
    pass


def test_catho_scraper_parses_filtered_remote_pj_listing() -> None:
    list_html = """
    <html><body>
      <article>
        <h2><a href="/vagas/desenvolvedor-php-senior-remoto/34371615/">Desenvolvedor PHP Senior / Remoto</a></h2>
        <p>Empresa Confidencial</p>
        <a href="/vagas/programador-senior/curitiba-pr/">Curitiba - PR (1)</a>
        <div>Entre 5 e 10 anos</div>
        <div>Estamos contratando Desenvolvedor Fullstack Sênior Home Office para atuação PJ.</div>
      </article>
    </body></html>
    """
    detail_url = "https://www.catho.com.br/vagas/desenvolvedor-php-senior-remoto/34371615/"
    detail_html = """
    <html><body>
      <div id="job-description">
        <h2>Sobre a vaga</h2>
        <div class="job-description">Atuação como desenvolvedor PHP sênior, 100% remoto, em regime PJ.</div>
      </div>
    </body></html>
    """

    scraper = _TestCathoDetailScraper(
        {
            "https://www.catho.com.br/vagas/programador-senior/?order=dataAtualizacao&contract_type_id%5B0%5D=6&work_model%5B0%5D=remote": list_html,
            detail_url: detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Desenvolvedor PHP Senior / Remoto"
    assert data.description == "Atuação como desenvolvedor PHP sênior, 100% remoto, em regime PJ."
    assert data.city == "Curitiba"
    assert data.state == "PR"
    assert data.attributes["company"] == "Empresa Confidencial"
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "pj"
    assert data.attributes["work_model"] == "remoto"
    assert data.attributes["experience_years"] == 5


def test_catho_scraper_enables_headful_fallback_for_antibot() -> None:
    config = CathoScraper.get_default_config()

    assert config.strategy.value == "browser_playwright"
    assert config.extra_config["playwright_headful_fallback"] is True
    assert config.extra_config["playwright_virtual_display_size"] == "1440x960"


def test_catho_scrape_url_parses_detail_page() -> None:
    detail_url = "https://www.catho.com.br/vagas/desenvolvedor-php-senior-remoto/34371615/"
    detail_html = """
    <html><head>
      <title>Vaga de Emprego de Desenvolvedor PHP Senior / Remoto, Curitiba / PR</title>
      <meta property="og:title" content="Vaga de Emprego de Desenvolvedor PHP Senior / Remoto, Curitiba / PR">
      <meta name="description" content="Vaga de Desenvolvedor PHP Senior / Remoto, Curitiba / PR, faixa salarial: De R$ 10.001,00 a R$ 15.000,00.">
    </head><body>
      <a title="Curitiba - PR (1)">Curitiba - PR (1)</a>
      <div id="job-description"><div class="job-description">Atuação com PHP e Laravel em regime PJ e remoto.</div></div>
    </body></html>
    """

    scraper = _TestCathoDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Desenvolvedor PHP Senior / Remoto"
    assert item.scraped_data.description == "Atuação com PHP e Laravel em regime PJ e remoto."
    assert item.scraped_data.city == "Curitiba"
    assert item.scraped_data.state == "PR"
    assert item.scraped_data.price == 10001.0
    assert item.scraped_data.attributes["salary_range"] == 10001.0


def test_infojobs_scraper_parses_card_container() -> None:
    list_html = """
    <html><body>
      <div class="js_vacancyLoad js_cardLink" data-href="/vaga-de-desenvolvedor-delphi-em-sao-paulo__11419087.aspx">
        <div class="d-flex gap-8 justify-content-between">
          <a href="/vaga-de-desenvolvedor-delphi-em-sao-paulo__11419087.aspx">
            <h2>Desenvolvedor Delphi Sênior</h2>
          </a>
          <div class="text-medium small text-nowrap">Hoje</div>
        </div>
        <div class="text-body">
          <a class="text-body text-decoration-none" href="https://www.infojobs.com.br/empresa-code-group__-9875599.aspx">CODE GROUP</a>
        </div>
        <div class="mb-8">São Paulo - SP</div>
        <div class="d-inline-flex flex-wrap mb-8 text-medium">
          <div><svg class="icon icon-money"></svg> A combinar</div>
          <div>Entre 5 e 10 anos</div>
          <div>Home office</div>
        </div>
        <div class="text-medium">
          Desenvolvedor Delphi Sênior Informações da vaga: Buscamos um desenvolvedor para atuação remota em contrato PJ.
        </div>
      </div>
    </body></html>
    """
    detail_url = "https://www.infojobs.com.br/vaga-de-desenvolvedor-delphi-em-sao-paulo__11419087.aspx"
    detail_html = """
    <html><body>
      <div class="pt-24 text-medium js_vacancyDataPanels js_applyVacancyHidden">
        Desenvolvedor Delphi Sênior\nResponsabilidades da vaga\nAtuação remota em contrato PJ com time distribuído.
      </div>
    </body></html>
    """

    scraper = _TestInfoJobsDetailScraper(
        {
            "https://www.infojobs.com.br/vagas-de-emprego-programador+s%c3%aanior-trabalho-home-office.aspx?tipocontrato=17": list_html,
            detail_url: detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Desenvolvedor Delphi Sênior"
    assert "Responsabilidades da vaga" in data.description
    assert "Atuação remota em contrato PJ" in data.description
    assert data.city == "São Paulo"
    assert data.state == "SP"
    assert data.attributes["company"] == "CODE GROUP"
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "pj"
    assert data.attributes["work_model"] == "remoto"
    assert data.attributes["experience_years"] == 5


def test_infojobs_scrape_url_parses_detail_page() -> None:
    detail_url = "https://www.infojobs.com.br/vaga-de-desenvolvedor-delphi-em-sao-paulo__11419087.aspx"
    detail_html = """
    <html><body>
      <h2>Desenvolvedor Delphi Sênior</h2>
      <div class="js_vacancyDataPanels">Responsabilidades da vaga\nAtuação remota em contrato PJ com time distribuído.</div>
      <script type="application/ld+json">
        {"@context":"http://schema.org","@type":"JobPosting","title":"Desenvolvedor Delphi Sênior","hiringOrganization":{"name":"CODE GROUP"},"jobLocation":{"address":{"addressLocality":"São Paulo","addressRegion":"SP"}}}
      </script>
    </body></html>
    """

    scraper = _TestInfoJobsDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Desenvolvedor Delphi Sênior"
    assert "Atuação remota em contrato PJ" in item.scraped_data.description
    assert item.scraped_data.city == "São Paulo"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.attributes["company"] == "CODE GROUP"


def test_infojobs_scraper_uses_detail_company_when_card_omits_company() -> None:
    list_html = """
    <html><body>
      <div class="js_vacancyLoad js_cardLink" data-href="/vaga-de-desenvolvedor-c-em-sao-paulo__11346835.aspx">
        <div class="d-flex gap-8 justify-content-between">
          <a href="/vaga-de-desenvolvedor-c-em-sao-paulo__11346835.aspx">
            <h2>Desenvolvedor C</h2>
          </a>
          <div class="text-medium small text-nowrap">Hoje</div>
        </div>
        <div class="mb-8">Ribeirão Preto - SP</div>
        <div class="d-inline-flex flex-wrap mb-8 text-medium">
          <div><svg class="icon icon-money"></svg> A combinar</div>
          <div>Entre 1 e 3 anos</div>
          <div>Home office</div>
        </div>
        <div class="text-medium">
          Desenvolvedor C para atuação remota com Progress e Datasul.
        </div>
      </div>
    </body></html>
    """
    detail_url = "https://www.infojobs.com.br/vaga-de-desenvolvedor-c-em-sao-paulo__11346835.aspx"
    detail_html = """
    <html><body>
      <h2>Desenvolvedor C</h2>
      <a href="https://www.infojobs.com.br/empresa-prime-consultoria__673344.aspx">Prime Consultoria</a>
      <div class="js_vacancyDataPanels">
        Desenvolvedor C para atuação remota com Progress e Datasul.
      </div>
      <script type="application/ld+json">
        {"@context":"http://schema.org","@type":"JobPosting","title":"Desenvolvedor C","hiringOrganization":{"name":"Prime Consultoria"},"jobLocation":{"address":{"addressLocality":"Ribeirão Preto","addressRegion":"SP"}}}
      </script>
    </body></html>
    """

    scraper = _TestInfoJobsDetailScraper(
        {
            "https://www.infojobs.com.br/vagas-de-emprego-programador+s%c3%aanior-trabalho-home-office.aspx?tipocontrato=17": list_html,
            detail_url: detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert data.title == "Desenvolvedor C"
    assert data.city == "Ribeirão Preto"
    assert data.state == "SP"
    assert data.attributes["company"] == "Prime Consultoria"


def test_bne_scraper_parses_embedded_payload() -> None:
    list_html = """
    <html><body>
      <input id="jobInfoLocal" value="[{&quot;Url&quot;:&quot;https://www.bne.com.br/vaga/programador/1&quot;,&quot;Function&quot;:{&quot;Name&quot;:&quot;programador&quot;},&quot;Attributions&quot;:&quot;Programador .net sênior, contratação pj, 100% remoto.&quot;,&quot;CompanyName&quot;:&quot;ITDone&quot;,&quot;AverageWage&quot;:&quot;R$ 12.000,00&quot;,&quot;StateAbbreviation&quot;:&quot;SP&quot;,&quot;City&quot;:{&quot;Name&quot;:&quot;São Paulo&quot;},&quot;Home_Office&quot;:true}]"/>
    </body></html>
    """
    detail_html = """
    <html><body>
      <h1>Vaga de Programador</h1>
      <div class="job__info atribuicoes__vaga">
        <h2>Atribuições</h2>
        <p>Programador .net sênior, contratação pj, 100% remoto.</p>
        <p>Início imediato.</p>
      </div>
      <div class="job__info descricao__vaga">
        <h2>Descrição Geral</h2>
        <p>Empresa de tecnologia em expansão.</p>
        <p>Projeto de alta disponibilidade para cliente enterprise.</p>
      </div>
    </body></html>
    """

    scraper = _TestBNEDetailScraper(
        {
            "https://www.bne.com.br/vagas-de-emprego-para-programador/?Page=1&Function=programador&HomeOffice=True&LinkType=Aut%C3%B4nomo&LinkType=Freelancer&LinkType=Tempor%C3%A1rio": list_html,
            "https://www.bne.com.br/vaga/programador/1": detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert data.title == "Vaga de Programador"
    assert "Programador .net sênior, contratação pj, 100% remoto." in data.description
    assert "Início imediato." in data.description
    assert "Empresa de tecnologia em expansão." in data.description
    assert "Projeto de alta disponibilidade para cliente enterprise." in data.description
    assert data.city == "São Paulo"
    assert data.state == "SP"
    assert data.price == 12000.0
    assert data.attributes["company"] == "ITDone"
    assert data.attributes["salary_range"] == 12000.0
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "pj"
    assert data.attributes["work_model"] == "remoto"


def test_bne_scrape_url_parses_detail_page() -> None:
    detail_url = "https://www.bne.com.br/vaga/programador/1"
    detail_html = """
    <html><body>
      <h1>Vaga de Programador</h1>
      <div class="job__info atribuicoes__vaga">
        <h2>Atribuições</h2>
        <p>Programador .net sênior, contratação pj, 100% remoto.</p>
        <p>Início imediato.</p>
      </div>
      <div class="job__info descricao__vaga">
        <h2>Descrição Geral</h2>
        <p>Empresa localizada na cidade de São Paulo/SP do ramo Informática, contrata Programador.</p>
        <p>Projeto de alta disponibilidade para cliente enterprise.</p>
      </div>
      <script type="application/ld+json">
        {"@context":"http://schema.org","@type":"JobPosting","title":"Programador","hiringOrganization":{"name":"ITDone"},"jobLocation":{"address":{"addressLocality":"São Paulo","addressRegion":"SP"}}}
      </script>
    </body></html>
    """

    scraper = _TestBNEDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Vaga de Programador"
    assert "Início imediato." in item.scraped_data.description
    assert "Empresa localizada na cidade de São Paulo/SP do ramo Informática, contrata Programador." in item.scraped_data.description
    assert "cliente enterprise" in item.scraped_data.description
    assert item.scraped_data.city == "São Paulo"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.attributes["company"] == "ITDone"


def test_bne_maps_autonomo_contract_to_pj() -> None:
    list_html = """
    <html><body>
      <input id="jobInfoLocal" value="[{&quot;Url&quot;:&quot;https://www.bne.com.br/vaga/programador/2&quot;,&quot;Titulo&quot;:&quot;Vaga de Programador&quot;,&quot;Attributions&quot;:&quot;Atuação remota com backend.&quot;,&quot;CompanyName&quot;:&quot;ITDone&quot;,&quot;AverageWage&quot;:&quot;R$ 8.000,00&quot;,&quot;StateAbbreviation&quot;:&quot;SP&quot;,&quot;City&quot;:{&quot;Name&quot;:&quot;São Paulo&quot;},&quot;Home_Office&quot;:true,&quot;LinkType&quot;:[&quot;Autônomo&quot;]}]"/>
    </body></html>
    """
    detail_url = "https://www.bne.com.br/vaga/programador/2"
    detail_html = """
    <html><body>
      <h1>Vaga de Programador</h1>
      <div class="job__info atribuicoes__vaga"><p>Atuação remota com backend.</p></div>
      <div class="job__info descricao__vaga"><p>Contrato: Autônomo.</p></div>
      <script type="application/ld+json">
        {"@context":"http://schema.org","@type":"JobPosting","title":"Programador","hiringOrganization":{"name":"ITDone"},"jobLocation":{"address":{"addressLocality":"São Paulo","addressRegion":"SP"}}}
      </script>
    </body></html>
    """

    scraper = _TestBNEDetailScraper(
        {
            "https://www.bne.com.br/vagas-de-emprego-para-programador/?Page=1&Function=programador&HomeOffice=True&LinkType=Aut%C3%B4nomo&LinkType=Freelancer&LinkType=Tempor%C3%A1rio": list_html,
            detail_url: detail_html,
        }
    )
    items = scraper.scrape()
    assert len(items) == 1
    assert items[0].scraped_data.attributes["contract_type"] == "pj"

    item = scraper.scrape_url(detail_url)
    assert item is not None
    assert item.scraped_data.attributes["contract_type"] == "pj"


def test_nerdin_scraper_parses_remote_pj_card() -> None:
    list_html = """
    <html><body>
      <div class="vaga-card">
        <h3 class="vaga-titulo">Engenheiro de Software Sênior<span class="vaga-nova-badge">NOVA</span></h3>
        <div class="vaga-salario">R$ 18.000,00 - R$ 20.000,00</div>
        <div class="vaga-empresa">Consultoria de Recrutamento e Seleção TI</div>
        <div class="vaga-local">Home Office/HO</div>
        <div class="vaga-icones">
          <i class="fas fa-home text-info" title="Home Office"></i>
          <i class="fas fa-briefcase text-primary" title="PJ"></i>
        </div>
        <div class="vaga-hashtags">
          <a class="hashtag">#sistemas</a>
          <a class="hashtag">#reactjs</a>
        </div>
        <a class="btn-ver-vaga" href="vaga_emprego/engenheiro-de-software-93726.php">Quero essa Vaga</a>
      </div>
    </body></html>
    """
    detail_url = "https://www.nerdin.com.br/vaga_emprego/engenheiro-de-software-93726.php"
    detail_html = """
    <html><body>
      <div id="sobre-pane">
        <div class="mb-2"><span class="vaga-salario">Salário a Combinar</span></div>
        <div class="mb-1">E-mail: contato@empresa.com</div>
        <div class="text-muted small mb-2">Publicada há 2 dias</div>
        <div class="py-2 px-3 mb-3">Sobre a Vaga</div>
        <div class="mb-3">
          📍 Atuação 100% remota.<br><br>
          Stack moderna com foco em APIs distribuídas.<br><br>
          🔎 O que você vai fazer<br>
          • Liderar integrações entre serviços.<br>
          • Evoluir observabilidade da plataforma.<br>
          <a class="btn btn-primary">Quero me Candidatar</a>
        </div>
      </div>
      <div id="requisitos-pane">
        🧠 Conhecimentos esperados<br><br>
        React<br>
        Microsserviços<br>
        Observabilidade<br><br>
        Experiência sólida com arquitetura distribuída.
        <div class="mt-2"><strong>Engenheiro de Software Sênior</strong></div>
        <div>Nível: Senior</div>
        <div>Contratação PJ.</div>
        <div class="d-lg-none">Seja Premium</div>
      </div>
    </body></html>
    """

    scraper = _TestNerdinDetailScraper(
        {
            "https://www.nerdin.com.br/vagas.php?filtro_area%5B%5D=3&filtro_area%5B%5D=5&filtro_area%5B%5D=1&filtro_area%5B%5D=4&filtro_area%5B%5D=2&filtro_home_office=1&filtro_pj=1": list_html,
            detail_url: detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Engenheiro de Software Sênior"
    assert "NOVA" not in data.title
    assert "Atuação 100% remota." in data.description
    assert "O que você vai fazer: Liderar integrações entre serviços; Evoluir observabilidade da plataforma." in data.description
    assert "Conhecimentos esperados: React; Microsserviços; Observabilidade." in data.description
    assert "Experiência sólida com arquitetura distribuída." in data.description
    assert "📍" not in data.description
    assert "🔎" not in data.description
    assert "🧠" not in data.description
    assert "Salário a Combinar" not in data.description
    assert "Quero me Candidatar" not in data.description
    assert "Seja Premium" not in data.description
    assert "Nível:" not in data.description
    assert "Contratação PJ." not in data.description
    assert data.price == 18000.0
    assert data.attributes["company"] == "Consultoria de Recrutamento e Seleção TI"
    assert data.attributes["salary_range"] == 18000.0
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "pj"
    assert data.attributes["work_model"] == "remoto"


def test_nerdin_scrape_url_parses_detail_page() -> None:
    detail_url = "https://www.nerdin.com.br/vaga_emprego/engenheiro-de-software-93726.php"
    detail_html = """
    <html><body>
      <h1>Analista de Dados Sênior<span class="vaga-nova-badge">NOVA</span></h1>
      <div id="sobre-pane">
        <div class="mb-2"><span class="vaga-salario">Salário a Combinar</span></div>
        <div class="py-2 px-3 mb-3">Sobre a Vaga</div>
        <div class="mb-3">
          📍 RJ e SP (modelo híbrido)<br>
          🌎 Demais regiões: 100% remoto<br><br>
          Buscamos alguém para atuar na linha de frente de dados.<br><br>
          🔎 O que você vai fazer<br>
          • Analisar dados em BigQuery.<br>
          • Criar dashboards no Power BI.
        </div>
      </div>
      <div id="requisitos-pane">
        🧠 Conhecimentos esperados<br><br>
        SQL<br>
        Power BI<br>
        BigQuery<br><br>
        Perfil colaborativo e senso de dono.
        <div class="mt-2"><strong>Analista de Dados Sênior</strong></div>
        <div>Nível: Senior</div>
        <div>Contratação PJ.</div>
      </div>
      <div class="related-jobs">R$ 0,00</div>
      <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting","title":"Analista de Dados Sênior","description":"📍 RJ e SP (modelo híbrido)\\n🌎 Demais regiões: 100% remoto","hiringOrganization":{"name":"Venha Para Nuvem"},"baseSalary":{"@type":"MonetaryAmount","currency":"BRL","value":{"@type":"QuantitativeValue","minValue":0,"maxValue":0}}}
      </script>
    </body></html>
    """

    scraper = _TestNerdinDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Analista de Dados Sênior"
    assert "NOVA" not in item.scraped_data.title
    assert "RJ e SP (modelo híbrido)." in item.scraped_data.description
    assert "O que você vai fazer: Analisar dados em BigQuery; Criar dashboards no Power BI." in item.scraped_data.description
    assert "Conhecimentos esperados: SQL; Power BI; BigQuery." in item.scraped_data.description
    assert "Perfil colaborativo e senso de dono." in item.scraped_data.description
    assert "📍" not in item.scraped_data.description
    assert "🌎" not in item.scraped_data.description
    assert "🧠" not in item.scraped_data.description
    assert item.scraped_data.attributes["company"] == "Venha Para Nuvem"
    assert "salary_range" not in item.scraped_data.attributes
    assert item.scraped_data.price is None
    assert "R$ 0,00" not in item.scraped_data.description
    assert item.scraped_data.attributes["contract_type"] == "pj"
    assert item.scraped_data.attributes["work_model"] == "remoto"


def test_vanhack_scraper_uses_detail_urls_from_list_page() -> None:
    list_html = """
    <html><body>
      <a href="/job/11738">Forward Deployed Engineer - AI Voice and Chat Platform (Fully Remote)</a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <meta property="og:url" content="https://vanhack.com/job/11738">
      <meta property="og:title" content="Senior Software Engineer - VanHack">
      <div id="vh-job-details-header-section">
        <p>Posted 4 days ago</p>
        <p>Senior Software Engineer</p>
        <p>Austin, TX</p>
        <span>$150,000 up to $200,000 USD/Annual</span>
      </div>
      <div id="vh-job-details-job-about-section">
        <div class="sc-eQsaeD">
          <p><strong>VanHack</strong> Remote product engineering role with backend and platform scope.</p>
          <p>Contract role for a senior backend engineer.</p>
        </div>
      </div>
    </body></html>
    """

    scraper = _TestVanHackDetailScraper(
        {
            "https://vanhack.com/jobs/remote-jobs-in-united_states": list_html,
            "https://vanhack.com/job/11738": detail_html,
        }
    )
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == "https://vanhack.com/job/11738"
    assert data.title == "Senior Software Engineer"
    assert data.city == "Austin"
    assert data.state is None
    assert data.price == 150000.0
    assert data.currency == "USD"
    assert data.attributes["company"] == "VanHack"
    assert data.attributes["salary_range"] == 150000.0
    assert data.attributes["salary_type"] == "anual"
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "pj"
    assert data.attributes["work_model"] == "remoto"
    assert data.links == ["https://vanhack.com/job/11738"]


def test_vanhack_scrape_url_parses_detail_page() -> None:
    detail_url = "https://vanhack.com/job/11738"
    detail_html = """
    <html><body>
      <meta property="og:url" content="https://vanhack.com/job/11738">
      <meta property="og:title" content="Senior Software Engineer - VanHack">
      <div id="vh-job-details-header-section">
        <p>Posted 4 days ago</p>
        <p>Senior Software Engineer</p>
        <p>Austin, TX</p>
        <span>$150,000 up to $200,000 USD/Annual</span>
      </div>
      <div id="vh-job-details-job-about-section">
        <div class="sc-eQsaeD"><p><strong>VanHack</strong> Remote contract role.</p></div>
      </div>
    </body></html>
    """

    scraper = _TestVanHackDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.url == detail_url
    assert item.scraped_data.title == "Senior Software Engineer"
    assert item.scraped_data.attributes["company"] == "VanHack"


def test_vanhack_normalizes_em_dash_in_title_and_description() -> None:
    detail_url = "https://vanhack.com/job/11739"
    detail_html = """
    <html><body>
      <meta property="og:url" content="https://vanhack.com/job/11739">
      <meta property="og:title" content="Senior Software Engineer — Platform - VanHack">
      <div id="vh-job-details-header-section">
        <p>Posted 4 days ago</p>
        <p>Senior Software Engineer — Platform</p>
        <p>Remote</p>
      </div>
      <div id="vh-job-details-job-about-section">
        <div class="sc-eQsaeD">
          <p><strong>VanHack</strong> Remote contract role — backend platform scope.</p>
          <p>Design APIs — mentor engineers.</p>
        </div>
      </div>
    </body></html>
    """

    scraper = _TestVanHackDetailScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Senior Software Engineer - Platform"
    assert item.scraped_data.description == "VanHack Remote contract role - backend platform scope. Design APIs - mentor engineers."


def test_tractian_scraper_parses_list_and_detail_pages() -> None:
    list_url = "https://careers.tractian.com/jobs?workType=remote&team=Back-End+Engineering"
    detail_url = "https://careers.tractian.com/jobs/ea1a5d4e-c9ac-4ff5-971f-6da45952bb4f"
    list_html = """
    <html><body>
      <a href="/jobs/ea1a5d4e-c9ac-4ff5-971f-6da45952bb4f">
        <h2>Senior Backend Software Engineer</h2>
        <p><span>Software Development</span><span> / </span><span>Back-End Engineering</span></p>
        <p><span>São Paulo, SP</span><span> / </span><span>Remote</span></p>
      </a>
    </body></html>
    """
    detail_html = """
    <html><body>
      <script>
        (self.__next_s=self.__next_s||[]).push([0,{"type":"application/ld+json","children":"{
          \"employmentType\": \"FULL_TIME\",
          \"datePosted\": \"2024-01-05T11:51:28.200Z\",
          \"hiringOrganization\": {\"name\": \"Tractian\"},
          \"jobLocation\": {\"address\": {\"addressLocality\": \"São Paulo\", \"addressRegion\": \"SP\", \"postalCode\": \"04711-020\", \"streetAddress\": \"R. Amaro Guerra, 415\"}},
          \"applicationUrl\": \"https://careers.tractian.com/jobs/ea1a5d4e-c9ac-4ff5-971f-6da45952bb4f\"
        }","id":"careers-job-specs"}])
      </script>
      <main>
        <h1>Senior Backend Software Engineer</h1>
        <div class="bg-slate-100">
          <article data-cid="job-description">Engineering at TRACTIAN</article>
          <section>
            <h3>Requirements</h3>
            <ul><li>5+ years of backend development experience.</li></ul>
          </section>
        </div>
      </main>
    </body></html>
    """

    scraper = _TestTractianScraper({list_url: list_html, detail_url: detail_html})
    items = scraper.scrape()

    assert len(items) == 1
    data = items[0].scraped_data
    assert items[0].url == detail_url
    assert data.title == "Senior Backend Software Engineer"
    assert data.city == "São Paulo"
    assert data.state == "SP"
    assert data.zip_code == "04711-020"
    assert data.street == "R. Amaro Guerra, 415"
    assert data.attributes["company"] == "Tractian"
    assert data.attributes["seniority"] == "senior"
    assert data.attributes["contract_type"] == "clt"
    assert data.attributes["work_model"] == "remoto"
    assert data.attributes["experience_years"] == 5
    assert data.links == [detail_url]


def test_tractian_scrape_url_parses_detail_page() -> None:
    detail_url = "https://careers.tractian.com/jobs/ea1a5d4e-c9ac-4ff5-971f-6da45952bb4f"
    detail_html = """
    <html><body>
      <script>
        (self.__next_s=self.__next_s||[]).push([0,{"type":"application/ld+json","children":"{
          \"employmentType\": \"FULL_TIME\",
          \"hiringOrganization\": {\"name\": \"Tractian\"},
          \"jobLocation\": {\"address\": {\"addressLocality\": \"São Paulo\", \"addressRegion\": \"SP\", \"postalCode\": \"04711-020\", \"streetAddress\": \"R. Amaro Guerra, 415\"}},
          \"applicationUrl\": \"https://careers.tractian.com/jobs/ea1a5d4e-c9ac-4ff5-971f-6da45952bb4f\"
        }","id":"careers-job-specs"}])
      </script>
      <main><h1>Senior Backend Software Engineer</h1><div class="bg-slate-100"><article data-cid="job-description">5+ years of backend development experience.</article></div></main>
    </body></html>
    """

    scraper = _TestTractianScraper({detail_url: detail_html})
    item = scraper.scrape_url(detail_url)

    assert item is not None
    assert item.scraped_data.title == "Senior Backend Software Engineer"
    assert item.scraped_data.city == "São Paulo"
    assert item.scraped_data.state == "SP"
    assert item.scraped_data.links == [detail_url]

# Mercado e Fontes de Vagas - Pesquisa de Sourcing (2026)

Pesquisa consolidada sobre **como obter vagas de emprego de forma programática no Brasil em 2026**: quais plataformas oferecem API, quais são gratuitas, quais agregam outras fontes, e o que isso significa para a estratégia de ingestão do `kids-jobs`.

> Conclusão executiva: as grandes plataformas **fecharam o acesso de leitura de vagas por API**. Não existe API pública e gratuita (Gupy, Google Empregos, Indeed, LinkedIn) que permita a um desenvolvedor individual buscar vagas. O caminho viável para o `kids-jobs` é **scraping responsável das fontes públicas + APIs de terceiros com tier grátis (JSearch) como complemento**. O dinheiro/dado de vaga foi deliberadamente trancado pelas plataformas para forçar parceria paga.

Data da pesquisa: 2026-06-13.

---

## 1. APIs oficiais das grandes plataformas

Resumo do que cada uma oferece para **ler/buscar vagas** (não confundir com APIs de publicar/gerenciar vaga, que são outra coisa).

| Plataforma | API pública de busca de vagas? | Grátis? | Para quem é a API que existe |
|---|---|---|---|
| **Gupy** | Não | Não | Empresas clientes (ATS): criar/listar/editar as **próprias** vagas e candidaturas. Exige Bearer Token gerado dentro da conta paga da empresa |
| **Google Empregos** | Não | - | Só existe o caminho inverso: markup `schema.org/JobPosting` que empresas adicionam para o Google **indexar** as vagas delas. Não há endpoint de leitura |
| **Indeed** | Não (descontinuada) | Não | A antiga Publisher API (busca de vagas) foi deprecada. O que sobrou é para anunciante: Sponsored Jobs API e Job Sync API |
| **LinkedIn** | Não | Não | Só via Talent Solutions (Recruiter System Connect, Apply Connect, Premium Job Posting), restrito a **empresas constituídas** parceiras, aprovação de semanas a meses, preço enterprise |

### Detalhes por plataforma

**Gupy.** A API documentada em [developers.gupy.io](https://developers.gupy.io/) é um produto B2B de ATS. Serve para a empresa cliente gerenciar as próprias vagas (`GET /jobs` lista as vagas *daquela* empresa, com o token *daquela* empresa). Não há endpoint oficial para varrer vagas de todas as empresas. Acesso exige ser cliente do SaaS pago (SETUP > Configurações Avançadas > Geração de Token).

**Google Empregos.** O Google **não oferece API de dados de vagas**. O recurso oficial é a marcação structured data que publishers adicionam nas páginas para o Google indexar. Para *ler* vagas do Google Empregos só via serviços terceiros que raspam o Google (pagos).

**Indeed.** A Publisher API que permitia busca de vagas foi **descontinuada** e está fechada para novas integrações. Pior: desde **1º de fevereiro de 2026**, no Brasil (entre outros países), a Sponsored Jobs API passou a **cobrar US$ 3 por chamada**. Não há rota gratuita de busca para candidato/dev.

**LinkedIn.** A mais fechada das três. Desde 2015 todo acesso exige o LinkedIn Partner Program. Dados de vaga vivem no Talent Solutions, abertos só a empresas constituídas parceiras. **Um desenvolvedor individual não consegue consultar vagas do LinkedIn por API oficial.**

---

## 2. Hubs e agregadores de vagas (gratuitos para o candidato)

Distinção crítica: **agregador** rastreia outras fontes e junta tudo; **portal** tem vagas próprias e não puxa dos outros.

### Agregadores de verdade ("Google dos empregos")

| Hub | Como funciona | Grátis? | Nota |
|---|---|---|---|
| **Google Empregos** | Agrega no resultado de busca: puxa de Indeed, LinkedIn, Gupy, Vagas.com, páginas de empresa | Sim | O mais centralizador que existe para o usuário final |
| **Indeed Brasil** | Maior agregador do mundo, indexa páginas de carreira, job boards e **vagas da Gupy** | Sim | Filtros avançados e alertas por e-mail grátis |
| **Jooble** | Rastreia vários sites e encaminha ao original | Sim | Menos polido |

### Portais grandes (vagas próprias, não agregam)

- **DivulgaVagas** - grátis, **sem cadastro** para ver vagas, +38 mil ativas, distribui por WhatsApp
- **LinkedIn** - forte em tech/fintech e networking, grátis para candidato
- **Vagas.com** e **InfoJobs** - alto volume, grátis para candidato
- **Catho** - **freemium**: ver e candidatar a muitas vagas exige assinatura paga
- **Gupy (portal.gupy.io)** - centraliza só empresas que usam a Gupy, não é cross-plataforma

### Hubs de tecnologia (relevantes para vagas dev)

- **Coodesh**, **ProgramaThor**, **Trampos.co** - vagas de tecnologia BR
- **Remotar** e **RemoteOK** - foco em remoto
- **GeekHunter** e **Revelo** - modelo invertido, empresas procuram o candidato

---

## 3. APIs de terceiros com tier gratuito

Para obter dados de vaga via API de verdade, o caminho são agregadores terceiros, alguns com tier grátis:

| API | Fonte dos dados | Tier grátis | Cobertura BR |
|---|---|---|---|
| **JSearch** (via RapidAPI) | Puxa do **Google for Jobs** + web aberta. Retorna JSON com vaga, empresa, salário, link de candidatura | Sim, com limite de requisições/mês | Boa (herda do Google Empregos). Aposta mais segura para BR |
| **Adzuna API** | Agregador próprio | Sim, com rate limit | Variável por país, confirmar volume BR antes de apostar |
| **Jooble API** | Agregador Jooble | Liberada sob solicitação, costuma ser grátis | Razoável |

Caveats honestos: tiers grátis têm limite baixo de chamadas (bom para projeto pessoal/MVP, não para produto em escala) e a cobertura de vagas brasileiras varia. **JSearch é a aposta mais segura para o BR** por herdar do Google.

---

## 4. Implicação para o kids-jobs

O `kids-jobs` é local-first e já opera por scraping de fontes. A pesquisa confirma que **scraping é a estratégia correta**, porque não há API oficial gratuita de leitura. Estratégia de sourcing recomendada:

1. **Scraping das fontes públicas** (já no produto) como base, respeitando intervalos e ToS.
2. **Endpoint público não-documentado das páginas de carreira da Gupy** (`empresa.gupy.io`) para empresas-alvo: a página consome uma API interna que retorna JSON, observável no DevTools > Network. Não-documentado, pode quebrar, mas funciona.
3. **JSearch (tier grátis)** como complemento para cobrir o que o Google Empregos agrega, sem precisar raspar o Google diretamente (frágil e contra ToS).
4. Evitar depender de Google/Indeed/LinkedIn por API: ou não existe, ou é pago/enterprise.

Referência de scraper Gupy da comunidade: [gupy-job-scrapper (GitHub)](https://github.com/DouglasFantoni/gupy-job-scrapper).

---

## 5. Riscos e ToS

- **Scraping é zona cinzenta.** Respeitar `robots.txt`, throttle entre requisições, não sobrecarregar o servidor. Para uso pessoal local-first o risco é baixo, mas existe.
- **Endpoints não-documentados quebram sem aviso** quando a plataforma muda o front. Tratar como frágeis e ter fallback.
- **Raspar Google/Indeed/LinkedIn diretamente viola os ToS deles** e pode levar a bloqueio de IP. Preferir JSearch/Adzuna para esses dados.
- **Tiers grátis têm cota.** Implementar cache e tratamento de rate limit para não estourar.

---

## Fontes

**Gupy:**
- [Gupy API - documentação oficial](https://developers.gupy.io/)
- [Listing jobs - Gupy Developers](https://developers.gupy.io/docs/listing-jobs)
- [How to use the Gupy API: Available operations - Suporte Gupy](https://suporte.gupy.io/s/suporte/article/How-to-use-the-Gupy-API-Available-operations?language=en_US)
- [gupy-job-scrapper - open source](https://github.com/DouglasFantoni/gupy-job-scrapper)

**Google Empregos:**
- [Guide to Google Jobs API and Alternatives - Scrapfly](https://scrapfly.io/blog/posts/guide-to-google-jobs-api-and-alternatives)

**Indeed:**
- [Indeed Publisher API - Get Job (Deprecated)](https://developer.indeed.com/docs/publisher-jobs/get-job)
- [Sponsored Jobs API usage policy - Indeed Partner Docs](https://docs.indeed.com/sponsored-jobs-api/sponsored-jobs-api-usage-policy)

**LinkedIn:**
- [LinkedIn API: What Exists, What's Restricted (2026) - Clura](https://clura.ai/blog/linkedin-api)
- [LinkedIn API complete guide 2026 - ConnectSafely](https://connectsafely.ai/articles/linkedin-api-complete-guide-2026)

**APIs de terceiros:**
- [JSearch - Jobs API for Real-Time Job Listings - OpenWeb Ninja](https://www.openwebninja.com/api/jsearch)

**Hubs e agregadores BR:**
- [Melhores Sites de Emprego no Brasil em 2026 - Divulga Vagas](https://divulgavagas.com.br/blog/melhores-sites-de-emprego-no-brasil-em-2026)
- [Sites de emprego no Brasil 2026, comparativo - Careerboom](https://careerboom.ai/en/us/blog/tool-review/brazil-job-platforms-2026)
- [9 melhores sites de emprego gratuitos - Mobills](https://www.mobills.com.br/blog/ganhar-dinheiro/melhores-sites-de-emprego/)

### Contexto para Agentes - Kids Jobs

#### Objetivo

`kids-jobs` é uma extração standalone das funcionalidades de empregos do workspace HUNT. O foco é uso pessoal para procurar trabalho, com operação simples e sem dependências do ecossistema original.

#### Regras de arquitetura

- O projeto deve continuar totalmente separado de `hunt-*`
- Não integrar RabbitMQ, Redis, OpenSearch, `hunt-agent` ou serviços de CPF/CNPJ
- O backend é um monólito local em `FastAPI + SQLite + APScheduler + Playwright`
- O frontend é `Next.js` sem autenticação
- O domínio ativo é apenas `jobs`

#### Estrutura real

```text
kids-jobs/
├── backend/
│   ├── adapters/
│   ├── application/
│   ├── configuration/
│   ├── scripts/
│   └── main.py
├── frontend/
│   ├── src/app/(dashboard)
│   ├── src/app/(dashboard)/vagas
│   ├── src/app/(dashboard)/resume
│   ├── src/app/(dashboard)/sources
│   ├── src/app/(dashboard)/scrapings
│   └── src/lib/
├── docker-compose.yml
└── agents.md
```

#### Backend

- Porta padrão: `8001`
- Banco padrão: `sqlite:///./kids-jobs.db`
- Tabelas relevantes:
  - `sc_market`
  - `gr_resume_documents`
  - `sources`
  - `categories`
  - `sc_rescrape_jobs`
  - `source_execution_history`
- O `MarketService.ingest_raw()` reaproveita o contrato de `ScrapedItem`
- O reprocessamento agenda jobs localmente e processa a URL com `scrape_url(url)`
- O seed carrega apenas scrapers de `jobs`

#### Scrapers ativos

- `bne`
- `catho`
- `infojobs`
- `nerdin`
- `remotar`
- `remoteok`
- `spassu`
- `telegram_jobs_ti`
- `tractian`
- `vanhack`
- `wellfound`
- `weworkremotely`

#### Frontend

- Sem login e sem middleware de autenticação
- Home renderiza dashboard operacional em `/`
- Menus válidos:
  - `/`
  - `/vagas`
  - `/resume`
  - `/sources`
  - `/scrapings`
- O dashboard agrega métricas de vagas, histórico de scraping, últimas vagas e estado das fontes
- Rotas herdadas fora do escopo redirecionam para `/vagas`
- O storage local do currículo usa a chave `kids-jobs:resume-draft:v1`

#### Contratos úteis

- Vagas: `GET /market`, `GET /market/count`, `POST /market/lookup`, `DELETE /market/{id}`, `POST /market/delete-batch`
- Fontes: `GET /api/v1/sources`
- Scrapings: `GET /api/v1/scrapers/config`, `POST /api/v1/scrapers/{source_id}/run`, `POST /api/v1/scrapers/run-all`
- Reprocessamento: `POST /api/v1/rescrape-jobs`, `POST /api/v1/rescrape-jobs/process`
- Currículo: `GET|PUT /api/v1/resume-document/`, `POST /api/v1/resume-document/send-email`

#### Operação local

- Backend:
  - `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python main.py`
- Frontend:
  - `cd frontend && npm ci && npm run dev`
- Docker:
  - `docker compose up --build`

#### Cuidados ao editar

- Preserve o isolamento do projeto novo; não reutilize serviços do HUNT por conveniência
- Se adicionar scraper novo, ele deve ser da vertical `jobs`
- Se mudar contrato ou fluxo local, atualize este `agents.md` e o `README.md`

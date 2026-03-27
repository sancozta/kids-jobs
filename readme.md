### Kids Jobs

Aplicação standalone para busca de vagas, currículo, dashboard operacional, fontes e scrapings de empregos.

#### Stack

- `frontend/`: Next.js App Router, sem login
- `backend/`: FastAPI + APScheduler + SQLite + Playwright
- Banco único local: SQLite
- Escopo: somente `jobs`

#### O que ficou de fora

- RabbitMQ
- `hunt-agent`
- integrações com `hunt-backend`, `hunt-cpf`, `hunt-cnpj` e notificações do ecossistema HUNT
- autenticação no frontend

#### Estrutura

```text
kids-jobs/
├── agents.md
├── docker-compose.yml
├── backend/
└── frontend/
```

#### Rodando localmente

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Frontend em `http://localhost:3000` e backend em `http://localhost:8001`.

#### Rodando com Docker

```bash
docker compose up --build
```

#### Fluxos principais

- Scraper executa localmente e persiste no `sc_market` via `LocalIngestAdapter`
- Reprocessamento usa tabela `sc_rescrape_jobs` + scheduler local, sem fila externa
- Currículo salva em SQLite e exporta PDF renderizando `/resume/export` no frontend via Playwright
- Envio de currículo por e-mail usa Resend quando configurado
- A home do frontend expõe um dashboard jobs-only com métricas de vagas, histórico de scraping, últimas vagas e fontes monitoradas

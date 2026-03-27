### Kids Jobs Backend

Backend monolítico local do `kids-jobs`.

#### Responsabilidades

- executar scrapers de `jobs`
- persistir vagas, fontes, categorias, histórico e fila de rescrape em SQLite
- expor API HTTP única para frontend e operação manual
- gerar PDF de currículo via Playwright
- enviar currículo por e-mail via Resend quando configurado

#### Ponto de entrada

```bash
python main.py
```

Leia também:

- `../README.md`
- `../agents.md`

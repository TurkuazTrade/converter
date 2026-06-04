# Turkuaz CRM

Internal CRM for Turkuaz Trade order operations. The active module converts customer Excel orders into a normalized final export, keeps order history, and maintains product/client reference data for matching.

The repository is organized as a small platform: one web app, one API, local data storage, and reserved folders for future workers, shared contracts, and deployment configuration.

## What Is Included

- Upload and parse Excel order files.
- Match order rows to clients and products.
- Maintain product and client reference directories.
- Configure product export exclusions.
- Generate final Excel exports from the provided template.
- Review converter history and unresolved items.

## Repository Structure

```text
apps/
  api/              FastAPI API, SQLAlchemy models, Alembic migrations, converter logic
  web/              React + TypeScript + Vite frontend
data/
  templates/        Excel templates used by exports
  storage/          Local source/export/quarantine file storage
docs/               Architecture notes
infra/              Reserved deployment/infrastructure documentation
packages/shared/    Reserved shared contracts/helpers
workers/            Reserved background worker boundaries
docker-compose.yml  Local development stack
```

## Quick Start With Docker

From the repository root:

```bash
docker compose up --build
```

Open the web app:

```text
http://localhost:7501
```

API base URL:

```text
http://localhost:8501/api/v1
```

The Docker stack mounts `./data` into the API container, so local SQLite data and generated files stay on the host.

## Default Local Credentials

Development settings auto-create users from `apps/api/.env.example`.

```text
Admin: admin@example.com / admin123
Test user: user@example.com / password
```

Change these before any non-local deployment.

## Manual API Setup

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Useful checks:

```bash
curl http://localhost:8501/api/v1/health
pytest
```

## Manual Web Setup

```bash
cd apps/web
npm install
npm run dev
```

Build check:

```bash
npm run build
```

The web app uses `VITE_API_URL` for API requests. Docker sets it to `/api/v1` and proxies to the API service.

## Identity Login

The converter frontend signs users in through Turkuaz Identity and stores the shared
`identity_access_token`. Converter API requests then use that JWT as `Authorization: Bearer <token>`.

For IIS/static frontend deployments, proxy these paths:

```text
IIS 7501 -> /api/* reverse proxy -> http://127.0.0.1:8501/api/*
IIS 7501 -> /identity-api/* reverse proxy -> http://127.0.0.1:8500/api/v1/*
```

After deployment, these checks should return JSON:

```text
http://SERVER_IP_OR_DOMAIN:7501/ready
http://SERVER_IP_OR_DOMAIN:7501/identity-api/ready
```

## Data And Storage

For local development:

```text
data/app.db
data/storage/source
data/storage/export
data/storage/quarantine
data/templates/template_zakaz.xlsx
```

Ignored runtime data should stay under `data/storage/*` and `data/app.db`. Keep `.gitkeep` files so storage directories exist in a clean checkout.

## Converter Configuration

Converter definitions live in:

```text
apps/api/app/converters/configs/
```

When adding a converter:

1. Add a JSON config with `type`, `version`, `sheet`, `header`, and `columns`.
2. Prefer config-driven parsing.
3. Add Python converter code only when the format cannot be expressed by config.
4. Add or update tests under `apps/api/tests/`.

## Development Rules

- Keep synchronous CRM behavior in `apps/api`.
- Add a worker only for slow, scheduled, retry-heavy, or externally fragile jobs.
- Put shared code in `packages/shared` only when at least two apps/workers need it.
- Do not commit local databases, generated exports, virtual environments, `node_modules`, or build outputs.

More architectural context is in `docs/ARCHITECTURE.md`.

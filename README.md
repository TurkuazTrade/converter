# Turkuaz Platform

Internal web platform for Turkuaz Trade operations. The current working module is the Excel order converter, but the repository is now structured so reports, integrations, and background workers can be added without reshuffling the project later.

## Structure

```text
apps/
  api/          FastAPI API, SQLAlchemy, Alembic, converters, matching, export
  web/          React + TypeScript + Vite frontend
workers/
  converter/    Future background Excel/file processing worker
  reports/      Future report generation worker
  integrations/ Future external API sync worker
packages/
  shared/       Future shared types/helpers/contracts
infra/          Future deployment and infrastructure profiles
data/           Local SQLite DB, file storage, Excel templates
docker-compose.yml
```

The recommended growth path is one user-facing web app, one main API, and separate workers only for slow or failure-prone tasks such as file conversion, scheduled reports, and external integrations.

## Local Docker

From the repository root:

```bash
docker compose up --build
```

Open:

```text
http://localhost:5173
```

The API runs on:

```text
http://localhost:8000/api/v1
```

## API Setup

```bash
cd apps/api
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m app.cli create-admin --email admin@example.com --password admin123 --full-name "Admin"
uvicorn app.main:app --reload
```

Healthcheck:

```bash
curl http://localhost:8000/api/v1/health
```

## Web Setup

```bash
cd apps/web
npm install
npm run dev
```

## Data

For local development, SQLite and files live under:

```text
data/app.db
data/storage/source
data/storage/export
data/storage/quarantine
data/templates/template_zakaz.xlsx
```

The API default paths assume it is run from `apps/api`. Docker overrides these paths to `/data/...`.

## Tests

Backend:

```bash
cd apps/api
pytest
```

Frontend:

```bash
cd apps/web
npm run build
```

## Adding A Converter

1. Add a JSON config under `apps/api/app/converters/configs/`.
2. Include `type`, `version`, `sheet`, `header`, `columns`, and optional `metadata`/`filters`.
3. Add converter-specific Python only when config-driven parsing cannot express the format.
4. Add or update tests under `apps/api/tests/`.

## When To Add A Worker

Keep business APIs in `apps/api` by default. Add a worker when the job is slow, scheduled, retry-heavy, or should not affect normal CRM/API responsiveness.

Good worker candidates:

- Excel conversion/import queues
- large reports
- scheduled exports
- external system synchronization
- webhook processing

## Русская Версия

Это теперь не просто модуль конвертера, а заготовка платформы. Текущий рабочий функционал остался прежним: загрузка заказов, парсинг Excel, сопоставление клиентов/товаров, выгрузка Excel и история. Структура подготовлена так, чтобы позже добавить отчеты, интеграции и фоновые задачи без болезненного переноса папок.

Основной принцип:

```text
apps/web -> apps/api -> database/storage
                    -> future workers
```

Пока не нужно выносить конвертер в отдельный сервис. Его лучше держать в API, а отдельный worker создать тогда, когда появятся очереди, долгие отчеты или нестабильные внешние интеграции.

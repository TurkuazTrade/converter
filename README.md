# Bishkek CRM Web Module

First web-based module of the future internal CRM. It replaces the desktop-only converter approach with a FastAPI + React architecture focused on order upload, preview, unresolved matching, reprocess, and export history.

## Structure

```text
backend/       FastAPI, SQLAlchemy 2.0, Alembic, services, converters
frontend/      Vite React TypeScript app
data/          SQLite DB, local storage, templates
docker-compose.yml
```

## Backend Setup

```bash
cd backend
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

Login:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}'
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Docker Compose

```bash
docker compose up --build
```

For MVP, SQLite is stored under:

```text
data/app.db
```

Local storage folders:

```text
data/storage/source
data/storage/export
data/storage/quarantine
```

## Migrations

Create/update database:

```bash
cd backend
alembic upgrade head
```

Create a new migration later:

```bash
alembic revision --autogenerate -m "message"
```

## Current Foundation Scope

Implemented:

- FastAPI app
- settings through `.env`
- logging
- CORS
- healthcheck endpoint
- SQLAlchemy 2.0 DB session
- Alembic initial migration
- models for users, products, product barcodes, clients, files, orders, order items, mappings, processing events
- JWT auth and password hashing
- automatic development admin bootstrap (`admin@example.com` / `admin123`)
- admin seed CLI
- LocalStorageService abstraction
- converter registry skeleton
- JSON converter configs for 8 networks
- real Excel parsing for Piton, Narodnyi, Globus, SPAR, Dostor, Asia Retail, DarkStore, Alma
- order upload with file save, duplicate hash detection, parsed snapshot, order items, strict reference matching, reprocess
- export service that opens `template_zakaz.xlsx`, builds a valid workbook, stores it, and exposes download after client/products are resolved
- basic products/clients Excel import
- pytest foundation tests
- Vite React TypeScript frontend workflow: login, upload, preview, reprocess, export, download, history

Stubbed for next phase:

- advanced manual unresolved mapping UI
- fuzzy client/product suggestions
- background queue/Celery-style processing
- PostgreSQL deployment profile

## Tests

```bash
cd backend
pytest
```

Included tests:

- DB metadata creates all expected tables
- healthcheck endpoint
- converter config loading
- export regression test against template contract
- real sample parser regression tests for all 8 networks when source files are present locally

## Adding a Converter

1. Add a JSON config under `backend/app/converters/configs/`.
2. Include:
   - `type`
   - `version`
   - `sheet`
   - `header`
   - `columns`
   - optional `metadata` and `filters`
3. Add parser-specific behavior only if config-driven parsing cannot express the format.

## Order Workflow Target

1. Upload Excel.
2. Store source file.
3. Detect duplicate by SHA256.
4. Detect converter.
5. Parse and save `orders.parsed_snapshot`.
6. Create order items.
7. Match products/clients.
8. If client or products are unresolved: `needs_review`.
9. Operator imports references or saves mappings.
10. Reprocess/rematch.
11. Export from template only after client/products are resolved.
12. Download export and keep history.

---

# Bishkek CRM Web Module - русская версия

Это foundation нового web-модуля будущей CRM. Старый desktop converter не переносится как архитектура: он остается только reference по бизнес-логике и Excel-форматам. Новый проект построен как FastAPI backend + React frontend.

## Структура

```text
backend/       FastAPI, SQLAlchemy 2.0, Alembic, services, converters
frontend/      React + TypeScript + Vite
data/          SQLite база, local storage, Excel templates
docker-compose.yml
```

## Запуск backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m app.cli create-admin --email admin@example.com --password admin123 --full-name "Admin"
uvicorn app.main:app --reload
```

Проверка:

```bash
curl http://localhost:8000/api/v1/health
```

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

Открыть в браузере:

```text
http://localhost:5173
```

## Docker

```bash
docker compose up --build
```

Docker Desktop должен быть запущен. SQLite база хранится в `data/app.db`, файлы заказов и экспортов - в `data/storage/`.

## Что уже реализовано

- FastAPI app, CORS, logging, healthcheck
- SQLAlchemy 2.0 models и Alembic migration
- таблицы users, products, product_barcodes, clients, files, orders, order_items, mappings, processing_events
- JWT auth, password hashing, CLI для первого admin
- автоматическое создание dev-admin при старте: `admin@example.com` / `admin123`
- StorageService abstraction с local filesystem реализацией
- ConverterRegistryService и config-driven converter skeleton
- JSON configs для piton, narodnyi, globus, spar, dostor, asia_retail, darkstore, alma
- рабочий парсинг Excel для piton, narodnyi, globus, spar, dostor, asia_retail, darkstore, alma
- upload с сохранением source-файла, SHA256 duplicate detection, parsed snapshot, order items, строгий reference matching, reprocess
- ExportService, который открывает `template_zakaz.xlsx`, сохраняет новый Excel и отдает download после сопоставления клиента/товаров
- базовый импорт товаров и клиентов из Excel
- pytest tests: DB, healthcheck, converter configs, export regression
- React UI: login, upload, preview, unresolved, history, products, clients

## Что пока stub

- расширенный unresolved workflow с ручным поиском товара прямо в таблице
- fuzzy suggestions для клиентов/товаров
- background processing через очередь
- PostgreSQL production profile

## Тесты

```bash
cd backend
pytest
```

## Как добавить новую сеть

1. Создать JSON config в `backend/app/converters/configs/`.
2. Описать aliases, sheet/header strategy, columns и version.
3. Если config-driven подхода не хватает, добавить отдельный converter-класс, не меняя core pipeline.

## Целевой workflow

1. Оператор загружает Excel.
2. Система сохраняет source file и SHA256 hash.
3. Определяется сеть/converter.
4. Parser сохраняет `orders.parsed_snapshot`.
5. Matching ищет клиента и товары.
6. Если клиент или товары не найдены, заказ уходит в `needs_review`.
7. Оператор импортирует справочники или вручную выбирает товары/клиента и сохраняет mappings.
8. Order можно reprocess без повторной загрузки.
9. Export строится строго из `template_zakaz.xlsx` только после полного сопоставления.
10. История хранит source, export, статусы и события обработки.

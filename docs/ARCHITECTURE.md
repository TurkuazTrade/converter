# Architecture Notes

## Current Shape

The platform is intentionally a modular monorepo:

```text
apps/web  -> user interface
apps/api  -> primary synchronous API and core domain logic
data      -> local development database, storage, templates
```

The converter module currently lives inside `apps/api` because it shares users, clients, products, orders, mappings, and export history with the rest of the CRM workflow.

## Future Shape

Workers should be introduced when a responsibility becomes slow, retry-heavy, scheduled, or externally fragile:

```text
apps/web
  |
apps/api
  |
database / storage / queue
  |
workers/converter
workers/reports
workers/integrations
```

## Boundaries

- `apps/api`: auth, users, clients, products, orders, converter configs, matching, exports, API contracts.
- `apps/web`: user-facing workflows only. It should not know internal worker details.
- `workers/*`: asynchronous processing with explicit inputs and outputs.
- `packages/shared`: shared contracts/helpers only when duplication becomes real.
- `infra`: compose/deployment profiles, reverse proxy, environment templates.

## Extraction Rule

Do not create a new service just because a feature is new. Extract when at least one is true:

- It needs independent scaling.
- It runs long jobs.
- It must retry external calls.
- Its failures should be isolated from the main API.
- It has a different deploy cadence.
- It has a clear domain boundary and stable interface.

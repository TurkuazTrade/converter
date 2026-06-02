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

- `identity-service`: source of truth for human users, branches, roles, permissions, login, and JWT claims.
- `apps/api`: converter domain data, branch-scoped clients/products/orders/files/mappings/dictionaries, matching, exports, API contracts.
- `apps/web`: user-facing workflows only. It should not know internal worker details.
- `workers/*`: asynchronous processing with explicit inputs and outputs.
- `packages/shared`: shared contracts/helpers only when duplication becomes real.
- `infra`: compose/deployment profiles, reverse proxy, environment templates.

## Branch Ownership

Branches are created and assigned to users in `identity-service`. The converter API does not own human-user branch assignment. On each authenticated request it reads Identity JWT claims, syncs a local shadow branch row when needed, and stores the current user's `branch_id` on converter-owned records.

Identity tokens should provide a numeric active branch claim:

```json
{
  "branch_id": 2,
  "active_branch_id": 2,
  "branch_code": "bishkek",
  "branch_name": "Bishkek",
  "branch": {
    "id": 2,
    "code": "bishkek",
    "name": "Bishkek"
  },
  "branch_permissions_by_id": {
    "2": ["converter.orders.read"]
  }
}
```

Converter tables keep `branch_id` for isolation and foreign keys. Imports, matching, product/client lookup, mappings, dictionaries, file history, orders, and exports are filtered by the current user's branch. The local `branches` table is only a shadow reference for stable IDs and names received from Identity.

## Extraction Rule

Do not create a new service just because a feature is new. Extract when at least one is true:

- It needs independent scaling.
- It runs long jobs.
- It must retry external calls.
- Its failures should be isolated from the main API.
- It has a different deploy cadence.
- It has a clear domain boundary and stable interface.

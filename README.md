# Veklom VNP

Standalone Veklom Nexus Protocol product surface.

## Live Surfaces

- Main site: `https://veklom.com`
- VNP entry: `https://veklom.com/vnp`
- Developer surface: `https://veklom.dev`

This repo is deployed through Coolify, not Vercel.

## Methodology

Public VNP copy must follow `VNP Methodology v1.0`.

VNP is cryptographic API telemetry for the machine-to-machine economy. The live product language is:

- VNP v1.0 Verification Stack
- Physical measurements
- Signed telemetry
- Route beacons
- Robust scoring
- x402 settlement evidence
- PGL audit trails
- Agent/runtime enforcement

Do not reintroduce stale dimension-count shorthand or locked legacy-spec public copy.

## Backend Wiring

The standalone VNP surface talks only to the real implementation backends:

- BYOS backend: `https://api.veklom.com`
- CAPPO governed runtime backend: `https://capi.veklom.com`

Local Vite proxy defaults:

- `/api/v1/*` -> BYOS backend
- `/v1/*` -> CAPPO backend

Relevant production routes:

- `/api/v1/vnp/metrics`
- `/api/v1/vnp/directory/realtime`
- `/api/v1/beacon/topology`
- `/api/v1/x402/*`
- `/v1/exec`

## Checks

```bash
cd frontend
npm run test:vnp-copy
npm run lint
npm run build
```

Status labels must remain truthful: `Live`, `Connected`, `Partially Implemented`, `Demo Mode`, `Methodology Target`, `Not Yet Wired`, `Config Incomplete`, `Disconnected`, `Auth Required`, or `Insufficient Evidence`.

## Backend runtime configuration

The deployed entrypoint is `app.main:app` (database-backed only). Environment variables (names only, never commit values):

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | production: yes | Async PostgreSQL URL. Production refuses to start without it. |
| `VNP_ENV` | recommended | `production` enables fail-closed startup checks. |
| `VNP_ALLOW_DEMO_DATA` | no (default `false`) | Enables the in-memory demo runtime under `/api/v1/demo/*`. Never active in production; production refuses to start if set. |
| `VNP_CORS_ALLOW_ORIGINS` | no | Comma-separated CORS allowlist. Production defaults to the veklom.com origins; wildcard is rejected. |
| `REDIS_URL` | for probe cache | Redis for batch probe-event dedup cache. |

Migrations:

```bash
alembic upgrade head
```

Backend tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

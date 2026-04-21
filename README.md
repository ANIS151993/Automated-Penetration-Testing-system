# PentAI Pro

PentAI Pro is a local-first, scope-safe penetration testing platform built for the lab bounded to `172.20.32.0/18`.

This repository now spans the Phase 1 foundation, the initial Safety Core, and the first live execution slice:

- FastAPI backend with database-backed health, engagement CRUD, approvals, and backend-issued gateway JWTs
- tamper-evident audit persistence for approvals and validated tool requests
- Flask-based Tool Gateway validation service with typed tool registry and mTLS server entrypoint
- production Dockerfiles for the backend and frontend instead of source-mounted dev containers
- Alembic baseline migrations plus a bootstrap step that stamps legacy databases before normal upgrades
- persisted execution artifacts for validated tool runs, plus parser-derived inventory and finding suggestions from execution evidence
- a live operator console for engagements, approvals, validations, live execution, and stored execution evidence
- Next.js frontend shell for operator workflows
- Docker Compose, Caddy, SQL, and deployment scripts for the command and weapon nodes

## Safety Invariants

The following invariants are non-negotiable:

- every tool action must be validated in the UI, backend, and Tool Gateway
- audit records must remain tamper-evident through chained SHA-256 hashes
- the LLM may propose typed actions but never execute raw shell
- Command Node to Weapon Node traffic must use mTLS
- tool output is untrusted input and must be isolated from control instructions

## Repo Layout

The layout follows the local PentAI architecture manual:

- `backend/`: FastAPI API, orchestration, safety core, and tests
- `frontend/`: Next.js operator console shell
- `tool-gateway/`: Flask gateway deployed to the Weapon Node
- `sql/`: bootstrap schema and future migrations
- `scripts/`: setup and bootstrap helpers

## Local Commands

The intended package managers are `uv` for Python and `pnpm` for JavaScript.

Backend:

```bash
cd backend
uv sync
uv run pytest
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
pnpm install
pnpm build
pnpm dev
```

Tool Gateway:

```bash
cd tool-gateway
uv sync
uv run pytest
uv run flask --app gateway.app run --debug
```

## Weapon Node Deployment

Generate the lab CA, backend client certificate, and weapon node server certificate:

```bash
./scripts/generate-certs.sh
```

Deploy the Tool Gateway to the weapon node over SSH with a real JWT secret:

```bash
export WEAPON_NODE_PASSWORD='...'
export PENTAI_GATEWAY_JWT_SECRET='replace-this-before-use'
./scripts/setup-weapon-node.sh
```

## Command Node Runtime

Build and start the command-node stack with the production images:

```bash
docker compose build backend frontend
docker compose up -d backend frontend caddy
```

The backend now persists generated report artifacts in the compose-managed
`backend-artifacts` volume and exposes them through the API:

- `POST /api/v1/engagements/{engagement_id}/reports`
- `GET /api/v1/engagements/{engagement_id}/reports`
- `GET /api/v1/reports/{report_id}`

Validated requests can also be executed as streamed runs and then reviewed later as stored evidence:

- `POST /api/v1/engagements/{engagement_id}/tool-invocations/{invocation_id}/execute-stream`
- `GET /api/v1/engagements/{engagement_id}/tool-executions`
- `GET /api/v1/engagements/{engagement_id}/tool-executions/{execution_id}`
- `POST /api/v1/engagements/{engagement_id}/tool-executions/{execution_id}/cancel`

Parser-derived operator guidance is now available without auto-creating findings:

- `GET /api/v1/engagements/{engagement_id}/inventory`
- `GET /api/v1/engagements/{engagement_id}/finding-suggestions`

The inventory endpoint now prefers parsed execution evidence over raw validated args when completed execution artifacts exist. The operator console also exposes parser-backed `Finding Suggestions` that can prefill the manual finding form.

Execution artifacts now include richer structured observations for:

- `nmap.service_scan`: parsed open services and banners
- `nmap.os_detection`: parsed OS fingerprints, device type, and CPE values when present
- `http_probe.fetch_headers`: parsed HTTP status, server banners, powered-by disclosures, and missing security-header checks

Execution artifacts also persist structured stderr diagnostics for common operational failures, including connection refusal and root-privilege requirements. The operator console surfaces these as `Execution Diagnostics`, and generated reports now count them through `summary.parsed_diagnostics_total`.

The live execution console now supports explicit operator cancellation for active runs. Timeout budgets remain defined by the typed gateway tool registry and are emitted into the stream as `timeout_seconds`, while timed-out runs are persisted with `status=timed_out`.

## Current Gaps

This scaffold intentionally leaves the following for subsequent phases:

- full PostgreSQL migration coverage beyond the current backend tables
- Redis-backed streaming and orchestration
- automatic certificate rotation and secret distribution
- real tool execution wrappers and parser implementations
- multi-format report rendering beyond the current JSON artifact export

# Fvspec Leaderboard

> **Note**: Symlinked from `CLAUDE.md` and `KNOWLEDGE.md`.

Public leaderboard for Lean 4 formal verification benchmarks (like SWEBench for FV).

**Features:** Secure sandboxed `lake build` execution, cryptographic attestations, multiple tracks (functional/mvcgen), dataset explorer (322 samples)

**Deployment:** https://fvspec-benchmark.galois.com

## Architecture

Three services via BullMQ (Redis):

| App        | Stack                     | Deployment |
| ---------- | ------------------------- | ---------- |
| **web**    | Next.js 16, static export | nginx/EC2  |
| **api**    | Hono, Drizzle, PostgreSQL | systemd    |
| **worker** | BullMQ, Docker sandbox    | systemd    |

**Flow:** Submit → API validates/enqueues → Worker builds/attests → API stores → Frontend displays

## Apps

### `packages/web` — Frontend

Next.js 16, Tailwind v4, shadcn/ui. Static export.

**Routes:** `/` (landing), `/leaderboard`, `/submit`, `/paper`, `/dataset/[id]` (322 samples)

**Development:** `npm run dev:web` (port 3000)

### `packages/api` — REST API

Hono, Drizzle ORM, PostgreSQL, BullMQ, Zod.

**Endpoints:** `/submit`, `/runs/:id`, `/leaderboard`, `/dataset/list`, `/dataset/:id`, `/results`

**Dataset:** Loads `fvspec.jsonl` (322 samples, 4.1MB) at startup, in-memory Map for O(1) lookups

**Development:** `npm run dev:api` (port 3002)

**Environment:** `DATABASE_URL`, `REDIS_URL`, `API_TOKEN`, `PORT`, `DATASET_PATH`

### `packages/worker` — Job Executor

BullMQ, execa, Docker SDK.

**Flow:** Pull job → clone repo → `lake build` in sandbox → generate attestation → POST to API

**Modes:** Docker (production, `--network none`) vs Host (dev, faster)

**Development:** `npm run dev:worker`

**Environment:** `REDIS_URL`, `API_BASE_URL`, `API_TOKEN`, `TOOLCHAIN_IMAGE`, `TIME_LIMIT_SEC`, `MEMORY_MB`

## Development

```bash
# Quick start
docker compose up -d
cp .env.example .env
npm install
npm run dev  # Runs all services

# Individual services
npm run dev:web / dev:api / dev:worker
npm run build / lint / typecheck
```

## Deployment

**Production:** https://fvspec-benchmark.galois.com (EC2, `/home/quinnd/fvspec/`)

**Architecture:** nginx (:80) → static files + API proxy (:3002) + worker (via Redis)

**Config files:** `operations/` (nginx/systemd, symlinked to system)

**Update:** `git pull && npm install && npm run build && sudo systemctl restart fvspec-{api,worker} && sudo nginx -t && sudo systemctl reload nginx`

**Infrastructure:** PostgreSQL, Redis, nginx, Node.js 20+, Docker

See `operations/DEPLOYMENT.md` for details.

## Code Style

**TypeScript:** Named imports, Zod, async/await, explicit return types
**Files:** kebab-case (scripts), PascalCase (components)
**Git:** Conventional commits, pass hooks

## Key Concepts

**Tracks:** Benchmark categories (functional, mvcgen) with separate scoring
**Attestations:** Cryptographically-signed build execution proof
**Job states:** Pending → Running → Succeeded/Failed/Cancelled
**Dataset:** 322 PBT samples (Python → Lean), future scale 30K+

## Status

**Completed:** Frontend, dataset explorer/API, worker attestations, operations configs
**In progress:** DB schema, real leaderboard API, SSL
**Missing:** OAuth, submission form, real-time tracking, S3 storage, monitoring

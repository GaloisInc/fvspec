# Fvspec Leaderboard

> **Note**: Symlinked from `CLAUDE.md` and `KNOWLEDGE.md`.

Public dataset explorer for Lean 4 formal verification benchmarks (like SWEBench for FV).

**Features:** Dataset explorer (322 samples), JSON API for dataset access

**Deployment:** https://fvspec-benchmark.galois.com

## Architecture

Two services:

| App     | Stack                     | Deployment |
| ------- | ------------------------- | ---------- |
| **web** | Next.js 16, static export | nginx/EC2  |
| **api** | Hono, in-memory dataset   | systemd    |

**Flow:** Frontend fetches dataset samples from API → API loads JSONL file at startup → serves via REST endpoints

## Apps

### `packages/web` — Frontend

Next.js 16, Tailwind v4, shadcn/ui. Static export.

**Routes:** `/` (landing), `/paper`, `/dataset` (explorer), `/dataset/[id]` (322 samples)

**Development:** `npm run dev:web` (port 3000)

### `packages/api` — REST API

Hono, Zod. No database required.

**Endpoints:** `/dataset/list`, `/dataset/stats`, `/dataset/:id`

**Dataset:** Loads `fvspec.jsonl` (322 samples, 4.1MB) at startup, in-memory Map for O(1) lookups

**Development:** `npm run dev:api` (port 3001)

**Environment:** `PORT`, `DATASET_PATH`, `NEXT_PUBLIC_API_URL`

## Development

```bash
# Quick start
cp .env.example .env
npm install
npm run dev  # Runs web + api services

# Individual services
npm run dev:web / dev:api
npm run build / lint / typecheck
```

## Deployment

**Production:** https://fvspec-benchmark.galois.com (EC2, `/home/quinnd/fvspec/`)

**Architecture:** nginx (:80) → static files + API proxy (:3001)

**Config files:** `operations/` (nginx/systemd, symlinked to system)

**Update:** `git pull && npm install && npm run build && sudo systemctl restart fvspec-{api,web} && sudo nginx -t && sudo systemctl reload nginx`

**Infrastructure:** nginx, Node.js 20+

See `operations/DEPLOYMENT.md` for details (if exists).

## Code Style

**TypeScript:** Named imports, Zod, async/await, explicit return types
**Files:** kebab-case (scripts), PascalCase (components)
**Git:** Conventional commits, pass hooks

## Key Concepts

**Tracks:** Benchmark categories (functional, mvcgen) for future evaluation
**Dataset:** 322 PBT samples (Python → Lean), future scale 30K+

## Status

**Completed:** Frontend, dataset explorer/API
**Removed:** Submission system, worker infrastructure, PostgreSQL, Redis, BullMQ
**Future:** Full leaderboard with submission system will be implemented as separate service

# Fvspec Leaderboard

> **Note**: Symlinked from `CLAUDE.md` and `KNOWLEDGE.md`.

Public dataset explorer for Lean 4 formal verification benchmarks (like SWEBench for FV).

**Features:** Dataset explorer (322 samples), JSON API for dataset access

**Deployment:** https://fvspec-benchmark.galois.com

## Architecture

Single Next.js package with an embedded Hono API:

- `src/` — Next.js app (app/, components/, lib/)
- `src/lib/api.ts` — Hono API mounted at `/api` via Next.js route handler (`src/app/api/[...path]/route.ts`)
- `server/index.ts` — Standalone Hono server (imports `src/lib/api.ts`, for local dev on port 3001)
- `src/lib/common.ts` — Barrel re-export replacing old `@fvspec/common` package

**No database required.** Dataset is pre-computed at build time via `npm run prebuild` (`scripts/precompute-dataset.ts`) from `DATASET_PATH` (local JSONL) or `DATASET_URL` (S3), then served from the bundled artifact. This avoids loading the full JSONL on every Vercel cold start.

### Web — Frontend

Next.js 16, Tailwind v4, shadcn/ui.

**Routes:** `/` (landing), `/paper`, `/dataset` (explorer), `/dataset/[id]` (322 samples)

### API — Endpoints

Hono, Zod. Embedded in Next.js via route handler, also runnable standalone.

**Endpoints:** `/api/dataset/list`, `/api/dataset/stats`, `/api/dataset/:id`

**Environment:** `PORT`, `DATASET_PATH`, `DATASET_URL`, `NEXT_PUBLIC_API_URL`

## Development

```bash
cp .env.example .env
npm install
npm run dev        # Runs both web (port 3000) + standalone api (port 3001) via concurrently

# Individual services
npm run dev:web    # Next.js dev server on port 3000 (API embedded at /api)
npm run dev:api   # Standalone Hono server on port 3001

# Other commands
npm run build / lint / typecheck
```

## Deployment

Deploys as a standard Next.js app. The Hono API is embedded via the Next.js route handler — no separate API process needed in production.

**Production:** https://fvspec-benchmark.galois.com

## Code Style

**TypeScript:** Named imports, Zod, async/await, explicit return types
**Files:** kebab-case (scripts), PascalCase (components)
**Git:** Conventional commits, pass hooks

## Key Concepts

**Tracks:** Benchmark categories (functional, mvcgen) for future evaluation
**Dataset:** 322 PBT samples (Python → Lean), future scale 30K+

## Status

**Completed:** Frontend, dataset explorer, embedded API
**Removed:** Submission system, worker infrastructure, PostgreSQL, Redis, BullMQ, separate API server for production, `operations/` infra configs
**Future:** Full leaderboard with submission system will be implemented as separate service

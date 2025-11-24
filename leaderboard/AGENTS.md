# Fvspec Leaderboard Website

> **Note**: This file is symlinked from `CLAUDE.md` and `KNOWLEDGE.md` to ensure consistent guidance across different AI code assistants.

## Overview

The fvspec leaderboard is a public-facing platform for tracking formal verification benchmark submissions. Think **SWEBench**, but for Lean 4 formal verification.

**What makes this different:** Secure CI backend that executes `lake build` on submitted repositories, producing cryptographically-signed attestations of verification results.

**Key features:**

- Public submission interface (GitHub repo + commit SHA)
- Secure sandboxed execution (Docker with resource limits)
- Cryptographic attestations for reproducibility
- Real-time job status tracking
- Leaderboard with multiple tracks (functional, mvcgen)
- **Dataset explorer** - Browse 322 benchmark samples (Python PBT → Lean specs)

**Deployment:** https://fvspec-benchmark.galois.com

---

## Architecture

Three-service architecture connected via **BullMQ** job queue (Redis):

| App                   | Purpose                              | Deployment      | Long-lived? |
| --------------------- | ------------------------------------ | --------------- | ----------- |
| **`packages/web`**    | Frontend (Next.js 16, static export) | nginx on EC2    | ❌          |
| **`packages/api`**    | HTTP API (Hono, Drizzle ORM)         | systemd service | ❌          |
| **`packages/worker`** | Background executor (BullMQ, Docker) | systemd service | ✅          |

**Data flow:**

1. User submits → POST to API
2. API validates, inserts DB record, enqueues to Redis
3. Worker clones repo, runs `lake build` in sandbox
4. Worker generates attestation, reports back to API
5. Frontend polls API for status, displays results

---

## Apps

### `packages/web` — Next.js Frontend

**Tech stack:** Next.js 16, Tailwind v4, shadcn/ui, TypeScript, Static export

**Routes:**

- `/` - Landing page (hero, about, top models, submit preview, paper abstract)
- `/leaderboard` - Full rankings with tabs (Functional, MVCGen, Overall)
- `/submit` - Submission instructions and FAQ
- `/paper` - Research paper content
- `/dataset` - Dataset explorer (currently redirects to `/dataset/341`)
- `/dataset/[id]` - Browse individual benchmark samples

**Dataset Explorer (`/dataset/[id]`):**

- Browse 322 Python property-based test samples
- View Python code + generated Lean (Spec, Impl, Tests)
- Sample selector dropdown + random button
- Metadata: variant, model, repo, faithfulness scores
- Warning: "Early development dataset - final will be 2+ OOMs larger (30,000+ samples)"

**Key UI features:**

- Sticky header with "Dataset" nav link
- Pre-alpha warning banners on all pages
- Dark mode support
- Fully responsive
- Static site generation (all routes pre-rendered)

**Development:**

```bash
pnpm dev:web    # http://localhost:3000
pnpm build:web  # Static export to out/
```

**Current state:** Homepage/leaderboard use mock data. Dataset explorer uses real API.

---

### `packages/api` — Hono REST API

**Tech stack:** Hono, Drizzle ORM, PostgreSQL, BullMQ, Zod validation

**Endpoints:**

- `POST /submit` - Accept new submission, enqueue job
- `GET /runs/:id` - Fetch submission status + results
- `GET /leaderboard` - Query ranked submissions by track
- `GET /dataset/list` - List all 322 samples (minimal data)
- `GET /dataset/:id` - Get full sample by ID (Python + Lean code)
- `POST /results` - (Internal) Worker callback with results

**Dataset loading:**

- Loads `fvspec.jsonl` (322 samples, 4.1MB) at API startup
- In-memory Map<sample_id, DatasetSampleDetail> for O(1) lookups
- Path: `DATASET_PATH` env var or `../../../benchmark/artifacts/dataset-out/fvspec.jsonl`

**Key responsibilities:**

- Validate submissions (Zod schemas)
- Database transactions (submissions, runs, results)
- Serve leaderboard + dataset data
- Enqueue jobs to Redis

**Development:**

```bash
pnpm dev:api    # http://localhost:3002 (note: port 3002, not 3001)
```

**Environment:**

```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379
API_TOKEN=secret-for-worker
PORT=3002
DATASET_PATH=/path/to/fvspec.jsonl  # optional override
```

---

### `packages/worker` — Background Job Executor

**Tech stack:** BullMQ, execa, Docker SDK, undici

**Execution flow:**

1. Pull job from `submissions` queue
2. Clone repo, checkout commit SHA
3. Run `lake build` (dockerized or host)
4. Collect artifacts (`results/summary.json`)
5. Hash artifacts, build attestation
6. POST results to API

**Execution modes:**

- **Docker mode** (production): Isolated container, `--network none`, resource limits
- **Host mode** (development): Local `lake`, faster testing

**Development:**

```bash
pnpm dev:worker  # Connects to Redis, listens for jobs
```

**Environment:**

```bash
REDIS_URL=redis://localhost:6379
API_BASE_URL=http://localhost:3002  # must match API port
API_TOKEN=secret-for-worker
TOOLCHAIN_IMAGE=lean:4.14.0  # optional
TIME_LIMIT_SEC=7200  # 2 hours
MEMORY_MB=16000
RUNNER_NAME=prototype-runner-01
```

**Attestation format:**

```typescript
{
  schema: "https://lean4-bench.org/attestation/v1",
  submissionId: 123,
  repoUrl: "https://github.com/user/repo",
  commitSha: "abc123...",
  toolchain: { imageDigest: "sha256:...", lean: "4.14.0" },
  runner: { name: "runner-01", trust: "internal" },
  artifacts: [{ path: "results/summary.json", sha256: "..." }],
  limits: { timeSec: 7200, memoryMB: 16000 }
}
```

---

## Development Workflow

### Quick Start

```bash
cd leaderboard

# 1. Start infrastructure
docker compose up -d

# 2. Copy/edit environment
cp .env.example .env

# 3. Install dependencies
pnpm install

# 4. Start all services
pnpm dev  # Runs web:3000, api:3002, worker
```

### Testing Dataset Explorer

```bash
# 1. Ensure API is running with dataset loaded
pnpm dev:api
# Check logs: "[dataset] Successfully loaded 322 samples"

# 2. Test API endpoints
curl http://localhost:3002/dataset/list | jq '.total'  # Should return 322
curl http://localhost:3002/dataset/341 | jq '.sample_name'

# 3. Start frontend
pnpm dev:web
# Visit http://localhost:3000/dataset/341
```

### Service-specific commands

```bash
pnpm dev:web / dev:api / dev:worker  # Individual services
pnpm build / lint / typecheck         # Build/quality checks
```

---

## Deployment

**Production:** https://fvspec-benchmark.galois.com (EC2 with nginx)

### Current Setup (EC2 Prototype)

**Server:** EC2 instance at `/home/quinnd/fvspec/`
**Domain:** `fvspec-benchmark.galois.com` (DNS managed by Galois IT)
**Config:** `leaderboard/operations/` directory (symlinked to system)

**Deployment architecture:**

```
Internet → nginx (:80) → ┬─ Static files (/home/quinnd/fvspec/leaderboard/packages/web/out)
                         ├─ API reverse proxy (:3002 → /api/*)
                         └─ Worker (via API/Redis)
```

**Nginx configuration:**

- `operations/nginx-leaderboard.conf` - Main site (static + API reverse proxy)
- `operations/nginx-api.conf` - Optional separate API subdomain (not used currently)
- Symlinked to `/etc/nginx/sites-available/`

**Systemd services:**

- `operations/fvspec-api.service` - API server (port 3002)
- `operations/fvspec-worker.service` - Background worker
- Symlinked to `/etc/systemd/system/`

**SSL setup (pending):**

```bash
# After DNS propagates
sudo certbot --nginx -d fvspec-benchmark.galois.com
```

**Update procedure:**

```bash
cd /home/quinnd/fvspec
git pull
pnpm install
pnpm build

# Restart services
sudo systemctl restart fvspec-api fvspec-worker
sudo nginx -t && sudo systemctl reload nginx
```

### Deployment Files (operations/)

**`nginx-leaderboard.conf`:**

- HTTP-only initially (SSL via certbot later)
- Static site: `/home/quinnd/fvspec/leaderboard/packages/web/out`
- API proxy: `/api/*` → `http://localhost:3002/`
- Aggressive caching for static assets (1 year)
- Client-side routing support (try_files fallback)

**`fvspec-api.service` / `fvspec-worker.service`:**

- User: `quinnd`
- WorkingDirectory: `/home/quinnd/fvspec/leaderboard/packages/{api,worker}`
- EnvironmentFile: `/home/quinnd/fvspec/leaderboard/.env`
- ExecStart: `/usr/bin/pnpm start`
- Restart: always

**Why symlinks?**

- Repository is single source of truth
- git pull updates all configs atomically
- Rollback capability via git
- Audit trail in git history

### Infrastructure Requirements

1. **PostgreSQL** - Submissions, runs, results
2. **Redis** - BullMQ job queue
3. **nginx** - Reverse proxy + static serving
4. **Node.js 20+** - Runtime for API/worker
5. **Docker** (optional) - Worker sandboxing

### Security

- Worker sandboxing: Docker `--network none`, resource limits
- API authentication: Token for worker ingestion endpoint
- Input validation: Zod schemas for all endpoints
- Rate limiting: (TODO) nginx rate limits

---

## Code Style

**TypeScript:**

- Named imports: `import { foo } from 'bar'`
- Zod for validation, async/await
- Explicit return types for exports

**File naming:**

- kebab-case: `job-schema.ts`, `dataset-explorer.tsx`
- PascalCase components: `DatasetExplorer.tsx`

**Git commits:**

- Conventional commits (`feat:`, `fix:`, `docs:`)
- Exhaustive bodies explaining "why"
- All pre-commit hooks must pass (format, typecheck, lint)

---

## Key Concepts

### Tracks

Benchmark categories (`functional`, `mvcgen`) with separate datasets, scoring, and rankings.

### Attestations

Cryptographically-signed proof of build execution with specific constraints (toolchain, limits, runner). Enables reproducibility and auditability.

### Job Lifecycle

1. **Pending** - Enqueued
2. **Running** - Worker executing
3. **Succeeded** - Build completed
4. **Failed** - Build error/timeout
5. **Cancelled** - User cancelled

### Dataset Samples

322 Python property-based tests (Hypothesis) with generated Lean specifications:

- **code**: Python PBT source
- **spec**: Lean specification with `sorry` placeholders
- **impl**: Lean implementation
- **tests**: Lean test cases
- **Metadata**: variant, model, repo_id, faithfulness scores

**Future scale:** 30,000+ samples (2+ orders of magnitude larger)

---

## Implementation Status

**✅ Completed:**

- Frontend pages (home, leaderboard, submit, paper, dataset)
- Dataset explorer with 322 samples
- Dataset API endpoints (list, get by ID)
- In-memory dataset caching
- Worker with attestation generation
- Operations directory with nginx/systemd configs
- Pre-alpha warning banners

**🚧 In Progress:**

- Database schema implementation
- Real API integration (currently mock data on leaderboard)
- SSL setup on production domain

**❌ Missing:**

- GitHub OAuth authentication
- Actual submission form
- Real-time status tracking UI
- Artifact storage (S3)
- Monitoring dashboard
- Public API docs (OpenAPI)
- Dataset summary statistics page (#122)

---

## Troubleshooting

**Worker not picking up jobs:**

- Check Redis: `redis-cli -u $REDIS_URL ping`
- Verify queue name: `submissions`
- Check worker logs for errors

**Dataset not loading:**

- Check API startup logs: "[dataset] Successfully loaded 322 samples"
- Verify `DATASET_PATH` or default path exists
- Check file permissions

**API port mismatch:**

- API runs on port 3002 (not 3001)
- Worker `API_BASE_URL` must match: `http://localhost:3002`
- `.env` file should have consistent ports

**Build timeouts:**

- Increase `TIME_LIMIT_SEC`
- Check for infinite loops
- Monitor memory usage (OOM before timeout)

---

## Related Documentation

- **Root project:** `/AGENTS.md` (benchmark generation)
- **Benchmark suite:** `/benchmark/AGENTS.md`
- **Operations:** `/leaderboard/operations/DEPLOYMENT.md` (detailed deployment guide)
- **FVAPPS paper:** [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)

**Questions?** Open an issue or see `/benchmark/ideas/` for research notes.

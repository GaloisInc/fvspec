# Fvspec Leaderboard Website

> **Note**: This file is symlinked from `CLAUDE.md` and `KNOWLEDGE.md` to ensure consistent guidance across different AI code assistants.

## Overview

The fvspec leaderboard is a public-facing platform for tracking formal verification benchmark submissions. Think **SWEBench**, but for Lean 4 formal verification.

**What makes this different:** Instead of just displaying static results, the leaderboard integrates with a secure CI backend that executes `lake build` on submitted repositories, producing cryptographically-signed attestations of verification results.

**Key features:**

- Public submission interface (GitHub repo + commit SHA)
- Secure sandboxed execution (Docker containers with resource limits)
- Cryptographic attestations for reproducibility
- Real-time job status tracking
- Leaderboard with multiple tracks (functional, mvcgen, etc.)

---

## Architecture

Three-service architecture connected via **BullMQ** job queue (Redis):

| App                   | Purpose                                                                              | Deployment                                         | Runs long-lived jobs? |
| --------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------- | --------------------- |
| **`packages/web`**    | Frontend SSR, static pages, user dashboard                                           | e.g. Vercel / nginx / static host                  | ❌                    |
| **`packages/api`**    | HTTP API — accepts `/submit`, `/runs`, `/leaderboard`                                | Container / service (short-lived request handlers) | ❌                    |
| **`packages/worker`** | Background executors — consumes BullMQ queues, does `lake build`, signs attestations | Dedicated VM / runner pool                         | ✅                    |

**Data flow:**

1. User submits via `packages/web` → POST to `packages/api`
2. API validates submission, inserts DB record, pushes job to Redis queue
3. `packages/worker` picks up job, clones repo, runs `lake build` in sandbox
4. Worker generates attestation, uploads artifacts, reports back to API
5. Web frontend polls API for status updates, displays results

---

## Apps

### `packages/web` — Next.js Frontend

**Tech stack:**

- Next.js 16 (App Router, React 19, React Compiler enabled)
- Tailwind CSS v4 + shadcn/ui components
- TypeScript
- lucide-react for icons
- Static site generation (all routes pre-rendered)

**Structure:**

```
src/
  app/
    layout.tsx           # Root layout with sticky header
    page.tsx             # Landing page (scrollable sections)
    leaderboard/
      page.tsx           # Full leaderboard with tabs and filtering
    submit/
      page.tsx           # Detailed submission instructions
    paper/
      page.tsx           # Full research paper content
  components/
    header.tsx           # Sticky navigation header
    leaderboard-table.tsx # Interactive table with search/sort
    ui/                  # shadcn/ui primitives (button, card, table, etc.)
  lib/
    utils.ts             # cn() helper for class merging
```

**Page Structure:**

**Home (`/`)** - Single scrollable page with sections:

1. **Hero** - Title, subtitle, CTAs to leaderboard and submit
2. **About** - Benchmark overview with 3 stat cards (200 problems, 2 tracks, 5 submissions)
3. **Top Models** - Table showing top 5 models, link to full leaderboard
4. **Submit** - Quick requirements, link to detailed instructions
5. **Paper** - Full abstract in clickable card, link to full paper
6. **Footer** - Links to FVAPPS and ARIA

**Leaderboard (`/leaderboard`)** - Full rankings:

- Tabbed interface (Functional, MVCGen, Overall)
- Interactive filtering (search by model/organization)
- Sorting (by rank, score, or date)
- Scoring explanation cards

**Submit (`/submit`)** - Comprehensive guide:

- Requirements checklist
- Repository structure examples
- 5-step evaluation process
- API documentation (coming soon)
- FAQ section

**Paper (`/paper`)** - Full research paper:

- Abstract, Introduction, Benchmark Design
- Infrastructure, Results, Related Work
- Conclusion, References, Acknowledgments
- Download PDF and arXiv links

**Key UI Features:**

- Sticky header with navigation to all pages + GitHub
- No client-side routing on homepage (pure scrolling)
- Hover effects and smooth transitions
- Dark mode support (via Tailwind CSS variables)
- Fully responsive (mobile-friendly)

**Data Models:**

```typescript
type Submission = {
  id: number
  rank: number
  model: string // e.g., "GPT-4o", "Claude 3.5 Sonnet"
  organization: string // e.g., "OpenAI", "Anthropic"
  track: string // "functional" | "mvcgen"
  score: number // Percentage (0-100)
  passRate: string // e.g., "175/200"
  avgTime: string // e.g., "45s"
  status: string // "verified" | "pending" | "failed"
  date: string // ISO date string
  commitSha: string // Git commit (7+ chars)
}
```

**shadcn/ui Components Used:**

- `Button` - CTAs, navigation links
- `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent` - Content containers
- `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell` - Leaderboard display
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` - Track selection on leaderboard page
- `Badge` - Status indicators (verified, pending), labels
- `Input` - Search field in leaderboard filtering
- `Select`, `SelectTrigger`, `SelectContent`, `SelectItem` - Sort dropdown
- `Label` - Form labels
- `Alert`, `AlertDescription` - Info banners (beta notice on submit page)

**Component Patterns:**

- Server Components by default (all pages)
- Client Components only where needed (`'use client'` in `leaderboard-table.tsx` for interactivity)
- Composition pattern (cards contain headers/content, tables contain rows)
- Utility-first styling with Tailwind CSS
- Dark mode via CSS variables (`--background`, `--foreground`, etc.)

**Development:**

```bash
pnpm dev:web          # Start dev server on :3000
pnpm build:web        # Production build (static export)
```

**Deployment:**

- Static export → Vercel/Netlify/Cloudflare Pages
- All routes pre-rendered at build time
- No server-side runtime needed

**Current State (Mock Data):**
The frontend currently uses hardcoded mock data defined in `page.tsx` files:

```typescript
// packages/web/src/app/page.tsx (top 5 for homepage)
// packages/web/src/app/leaderboard/page.tsx (full dataset)
const mockSubmissions = [
  { id: 1, rank: 1, model: 'GPT-4o', organization: 'OpenAI', ... },
  // ...
]
```

**Migration to Real API:**
Once `packages/api` is fully implemented with database:

1. Replace mock data with `fetch()` calls to API endpoints
2. Add loading states and error handling
3. Consider adding React Query for caching and real-time updates
4. For static builds, fetch data at build time or use ISR (Incremental Static Regeneration)

---

### `packages/api` — Hono REST API

**Tech stack:**

- Hono (lightweight web framework)
- Drizzle ORM + PostgreSQL
- BullMQ (job queue client)
- Zod for validation
- Pino for logging

**Endpoints:**

- `POST /submit` — Accept new submission, enqueue job
- `GET /runs/:id` — Fetch submission status + results
- `GET /leaderboard` — Query ranked submissions by track
- `POST /ingest` — (Internal) Worker callback with results

**Structure:**

```
src/
  index.ts           # Main app, routes
  db/
    schema.ts        # Drizzle schema definitions
    migrations/      # SQL migration files
  lib/
    queue.ts         # BullMQ queue client
    auth.ts          # API token validation (for worker ingestion)
```

**Key responsibilities:**

- Validate submissions (Zod schemas)
- Rate limiting / spam protection
- Database transactions (submissions, runs, results)
- Enqueue jobs to Redis queue
- Serve leaderboard data with pagination

**Development:**

```bash
pnpm dev:api          # Start dev server on :3001
```

**Environment variables:**

```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379
API_TOKEN=secret-for-worker-ingestion
PORT=3001
```

---

### `packages/worker` — Background Job Executor

**Tech stack:**

- BullMQ Worker
- execa for subprocess management
- Docker SDK (for sandboxed execution)
- undici for HTTP ingestion

**Structure:**

```
src/
  worker.ts                # Main worker loop
  executors/
    lean.ts                # Lean build executor (docker + host modes)
  lib/
    attestation.ts         # Build attestation objects
    exec.ts                # Subprocess utilities
    hash.ts                # SHA-256 file hashing
    job-schema.ts          # Zod schemas for job data
    report.ts              # POST results back to API
```

**Execution flow:**

1. Pull job from `submissions` queue
2. Clone repo to temp directory
3. Checkout specified commit SHA
4. Run `lake build` (dockerized or host tooling)
5. Collect artifacts (`results/summary.json`)
6. Hash artifacts, build attestation
7. POST results to API `/ingest` endpoint

**Execution modes:**

- **Docker mode** (production): Runs build in isolated container
  - Network disabled (`--network none`)
  - Memory/CPU limits enforced
  - Timeout via `timeout` command
- **Host mode** (development): Uses local `lake` installation
  - Faster for testing
  - No sandboxing

**Key files:**

- `lean.ts:7-104` — Main build orchestration
- `attestation.ts:1-17` — Cryptographic attestation format
- `worker.ts:11-61` — BullMQ worker with retry logic

**Development:**

```bash
pnpm dev:worker       # Start worker (listens to Redis)
```

**Environment variables:**

```bash
REDIS_URL=redis://localhost:6379
API_BASE_URL=http://localhost:3001
API_TOKEN=secret-for-worker-ingestion
TOOLCHAIN_IMAGE=lean:4.14.0  # Docker image (optional)
TIME_LIMIT_SEC=7200           # 2 hours
MEMORY_MB=16000               # 16 GB
ARTIFACTS_DIR=/tmp/leaderboard_artifacts
RUNNER_NAME=runner-01
RUNNER_TRUST=internal         # internal|partner|community
WORKER_CONCURRENCY=1          # Parallel jobs
```

**Attestation format:**

```typescript
{
  schema: "https://lean4-bench.org/attestation/v1",
  submissionId: 123,
  repoUrl: "https://github.com/user/repo",
  commitSha: "abc123...",
  trackId: "functional",
  toolchain: { imageDigest: "sha256:...", lean: "4.14.0", lake: "..." },
  runner: { name: "runner-01", trust: "internal" },
  startedAt: "2025-10-27T12:00:00Z",
  finishedAt: "2025-10-27T12:05:00Z",
  artifacts: [{ path: "results/summary.json", sha256: "..." }],
  limits: { timeSec: 7200, memoryMB: 16000 }
}
```

---

## Development Workflow

### Local Development Setup

**Prerequisites:**

- Node.js >= 20
- pnpm (via `corepack enable` or global install)
- Docker & Docker Compose
- (Optional) Lean 4 toolchain if running worker without Docker sandboxing

**Quick Start:**

```bash
cd leaderboard

# 1. Start infrastructure (Postgres + Redis)
docker compose up -d

# 2. Copy environment variables
cp .env.example .env
# Edit .env if needed (defaults work for local dev)

# 3. Install dependencies
pnpm install

# 4. (Future) Run database migrations when schema exists
# cd packages/api && pnpm exec drizzle-kit push && cd ../..

# 5. Start all services in parallel
pnpm dev
```

**What runs:**

- `packages/web` on http://localhost:3000 (Next.js dev server)
- `packages/api` on http://localhost:3001 (Hono with tsx watch)
- `packages/worker` as background process (tsx watch, connects to Redis)

**Stopping services:**

```bash
# Stop application services (Ctrl+C in terminal)
# Stop infrastructure
docker compose down
```

### Service-specific commands

```bash
# Frontend only
pnpm dev:web

# API only
pnpm dev:api

# Worker only
pnpm dev:worker

# Build all
pnpm build

# Lint all
pnpm lint

# Type check
pnpm typecheck
```

### Testing a submission locally

```bash
# 1. Start API + worker
pnpm dev:api &
pnpm dev:worker &

# 2. Submit a test job
curl -X POST http://localhost:3001/submit \
  -H "Content-Type: application/json" \
  -d '{
    "repoUrl": "https://github.com/user/lean-project",
    "commitSha": "abc123",
    "trackId": "functional",
    "payload": {}
  }'

# 3. Check job status
curl http://localhost:3001/runs/123

# 4. Monitor worker logs
# (worker will clone repo, run lake build, report results)
```

---

## Code Style

**TypeScript:**

- Use `import { foo } from 'bar'` (not `import * as`)
- Zod for all data validation
- Async/await over promises
- Explicit return types for exported functions

**File naming:**

- kebab-case for files: `job-schema.ts`, `lean-executor.ts`
- PascalCase for components: `LeaderboardTable.tsx`

**Git commits:**

- Conventional commits (`feat:`, `fix:`, `docs:`, etc.)
- Exhaustive bodies explaining the "why"
- All pre-commit hooks must pass

---

## Deployment Considerations

**⚠️ This is NOT a standard Vercel-only deployment!**

The frontend (`packages/web`) can be deployed to Vercel/Netlify/Cloudflare Pages as a static site, but you need separate hosting for the backend services (`packages/api` + `packages/worker`) that require long-running processes and persistent infrastructure.

### Deployment Options

**Option 1: Split Deployment (Frontend + Backend)**

**Frontend:**

- Platform: Vercel, Netlify, or Cloudflare Pages
- Deploy: `packages/web` as static site
- Config: Set `NEXT_PUBLIC_API_URL` to point to your API

**Backend (API + Worker + Database):**

- Platform options:
  - **Railway** - Easiest, all-in-one platform with Postgres + Redis + app hosting
  - **Fly.io** - Good for Docker-based deployments, supports persistent volumes
  - **Render** - Simple platform with database + web service + background workers
  - **AWS/GCP/Azure** - Full control, more setup (ECS/Cloud Run/Container Apps)
  - **Self-hosted VPS** - Docker Compose on DigitalOcean/Hetzner/etc.

**Database Services:**

- PostgreSQL: Neon, Supabase, Railway DB, AWS RDS, or self-hosted
- Redis: Upstash, Redis Cloud, Railway Redis, ElastiCache, or self-hosted

**Option 2: All-in-One Platform**

Deploy all three services to a single platform:

- **Railway** (recommended for simplicity)
- **Fly.io** (better for scaling)
- **Render** (middle ground)

These platforms can host:

- Web service (Next.js SSR or static + serve)
- API service (Hono server)
- Worker service (background process)
- Managed Postgres + Redis

**Option 3: Self-Hosted (VPS with Docker Compose)**

Single VPS running Docker Compose with all services:

```bash
# On your VPS
git clone <repo>
cd leaderboard
cp .env.example .env
# Edit .env with production values
docker compose -f docker-compose.prod.yml up -d
```

Cost-effective but requires sysadmin experience.

### Production Infrastructure Requirements

1. **PostgreSQL** — Persistent storage for submissions/results
2. **Redis** — Job queue (BullMQ)
3. **Object storage** (S3/R2) — Artifact logs (optional but recommended)
4. **Worker VMs** — Isolated runners with Docker + Lean toolchain
5. **Web/API hosts** — Container platform or VPS

### Security

- **Worker sandboxing:** Docker with `--network none`, resource limits
- **API authentication:** Token-based auth for worker ingestion endpoint
- **Rate limiting:** Prevent submission spam
- **Input validation:** Never trust repoUrl/commitSha without sanitization

### Scalability

- **Horizontal worker scaling:** Add more worker VMs, increase `WORKER_CONCURRENCY`
- **Queue priority:** Add priority queues for premium users
- **Result caching:** Cache leaderboard queries in Redis

### Monitoring

- **Metrics:** Job completion rate, avg build time, failure reasons
- **Alerts:** Worker downtime, queue backlog > threshold
- **Logs:** Centralized logging (Pino → Loki/CloudWatch)

---

## Key Concepts

### Tracks

Different benchmark categories (e.g., `functional`, `mvcgen`). Each track has its own:

- Dataset of problems
- Scoring criteria
- Leaderboard ranking

### Attestations

Signed objects proving a build was executed with specific constraints:

- Toolchain version (Lean/Lake)
- Resource limits (time, memory)
- Runner identity (internal/partner/community trust levels)
- Artifact hashes (SHA-256)

**Purpose:** Reproducibility and auditability. Anyone can verify that a submission genuinely built under declared constraints.

### Job lifecycle

1. **Pending** — Enqueued, waiting for worker
2. **Running** — Worker executing `lake build`
3. **Succeeded** — Build completed, artifacts uploaded
4. **Failed** — Build error / timeout / OOM
5. **Cancelled** — User-requested cancellation

### Artifacts

Build outputs stored for analysis:

- `results/summary.json` — Metrics (pass@k, time, etc.)
- `build.log` — Full build output
- (Future) Proof traces, coverage reports

---

## Implementation Status

**✅ Completed (packages/web):**

- Landing page with scrollable sections (about, top models, submit preview, paper abstract)
- Full leaderboard page with tabs (Functional, MVCGen, Overall)
- Interactive leaderboard table (search, sorting by rank/score/date)
- Submit page with detailed instructions and FAQ
- Paper page with full research content
- Sticky header navigation
- Dark mode support
- Responsive design
- Static site generation (all routes pre-rendered)

**✅ Completed (packages/worker):**

- BullMQ worker consuming submissions queue
- Lean build executor (Docker + host modes)
- Attestation generation with SHA-256 hashing
- Resource limits enforcement (time, memory)
- Error handling and retry logic

**🚧 In Progress:**

- Database schema (`packages/api/src/db/schema.ts`)
- API implementation (currently has stubs)
- Connecting frontend to real API (currently uses mock data)

**❌ Missing:**

- Authentication (GitHub OAuth for submissions)
- Actual submission form (currently just documentation)
- Real-time job status tracking UI
- Webhook integration (auto-submit on new commits)
- Artifact storage (S3 uploads for build logs)
- Metrics dashboard (Grafana)
- Public API docs (OpenAPI spec)
- Email notifications for submission results
- Submission history per organization

**Research questions:**

- How to score partial verification (some theorems proven)?
- Multi-track aggregation (overall leaderboard)?
- Cost accounting (CPU-hours per submission)?
- How to handle benchmark updates without invalidating old submissions?

---

## Research Paper Content

The `/paper` page contains the full fvspec research paper with the following structure:

**Abstract** (also shown on homepage):

- Introduces fvspec as a benchmark for evaluating AI on formal verification
- Emphasizes real-world tests over synthetic problems
- Describes two verification paradigms (functional, mvcgen)
- Highlights structural faithfulness metrics and LSP/MCP integration
- Presents initial results from leading models

**Main Sections:**

1. **Introduction** - Motivation, challenges in evaluating AI-assisted formal verification
2. **Benchmark Design** - Problem selection, verification tracks (Functional, MVCGen), evaluation metrics
3. **Infrastructure** - MCP integration for LSP, sandboxed evaluation, cryptographic attestations
4. **Initial Results** - Performance of GPT-4o, Claude 3.5 Sonnet, Gemini 2.0 Flash across tracks
5. **Related Work** - FVAPPS, LeanDojo, ProofGPT/PISA, SWE-bench
6. **Conclusion** - Future directions (multi-prover support, LSP feedback loops, fine-grained analysis)
7. **References** - Key citations including FVAPPS paper
8. **Acknowledgments** - ARIA funding, Lean community support

**Key Claims:**

- 200 real-world problems from GitHub (not synthetic)
- Focus on specification quality over proof completion
- Cryptographic attestations for reproducibility
- LSP/MCP integration for interactive development
- Two verification paradigms to test different reasoning styles

---

## Related Documentation

- **Root project:** `/AGENTS.md` (benchmark generation system)
- **Benchmark suite:** `/benchmark/AGENTS.md`
- **FVAPPS paper:** [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)
- **Paper page:** `/leaderboard/packages/web/src/app/paper/page.tsx` (full content)

---

## Troubleshooting

**Worker not picking up jobs:**

- Check Redis connection: `redis-cli -u $REDIS_URL ping`
- Verify queue name matches (`submissions`)
- Check worker logs for errors

**Build timeouts:**

- Increase `TIME_LIMIT_SEC` env var
- Check for infinite loops in submitted code
- Monitor memory usage (may OOM before timeout)

**Attestation verification failed:**

- Ensure artifact files weren't modified post-build
- Check SHA-256 hashes match
- Verify toolchain image digest

---

**Questions?** Open an issue or see `/benchmark/ideas/` for research notes.

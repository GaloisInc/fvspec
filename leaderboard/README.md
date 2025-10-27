# fvspec Leaderboard

Public-facing leaderboard website for the fvspec formal verification benchmark.

## Quick Start (Local Development)

### Prerequisites

- Node.js >= 20
- pnpm (installed globally or via `corepack enable`)
- Docker & Docker Compose
- (Optional) Lean 4 toolchain if running worker without Docker

### 1. Start Infrastructure

```bash
# Start Postgres + Redis
docker compose up -d

# Verify they're running
docker compose ps
```

### 2. Setup Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env if needed (defaults work for local dev)
```

### 3. Install Dependencies

```bash
pnpm install
```

### 4. Run Services

**Option A: All services in parallel**

```bash
pnpm dev
```

**Option B: Individual services**

```bash
# Terminal 1: Web frontend (http://localhost:3000)
pnpm dev:web

# Terminal 2: API server (http://localhost:3001)
pnpm dev:api

# Terminal 3: Worker (processes jobs from Redis queue)
pnpm dev:worker
```

### 5. View the Site

Open http://localhost:3000 in your browser.

**Note:** Currently uses mock data. API endpoints return stubs until database schema is implemented.

## Architecture

Three-service monorepo:

- **packages/web** - Next.js 16 static site (currently mock data)
- **packages/api** - Hono REST API (stub implementation)
- **packages/worker** - BullMQ worker for Lean builds

See `AGENTS.md` for detailed documentation.

## Development Commands

```bash
# Development
pnpm dev              # Run all services in parallel
pnpm dev:web          # Next.js dev server
pnpm dev:api          # API dev server (tsx watch)
pnpm dev:worker       # Worker dev mode (tsx watch)

# Build
pnpm build            # Build all packages
pnpm build:web        # Build frontend
pnpm build:api        # Build API
pnpm build:worker     # Build worker

# Quality
pnpm typecheck        # Type-check all packages
pnpm lint             # Lint all packages
pnpm test             # Run tests (stubs currently)
pnpm clean            # Clean build artifacts

# Production
pnpm start:web        # Start production Next.js server
pnpm start:api        # Start production API server
pnpm start:worker     # Start production worker
```

## Project Structure

```
leaderboard/
├── packages/
│   ├── web/          # Next.js frontend
│   ├── api/          # Hono REST API
│   └── worker/       # BullMQ worker
├── docker-compose.yml    # Postgres + Redis for local dev
├── .env.example          # Environment variables template
└── package.json          # Workspace root
```

## Deployment

**This is NOT a standard Vercel-only deployment.** You need:

1. **Frontend (packages/web):**
   - Can deploy to Vercel/Netlify/Cloudflare Pages
   - Currently static with mock data
   - Will need API_BASE_URL env var to connect to API

2. **Backend (packages/api + packages/worker):**
   - Needs a platform that supports long-running processes
   - Options: Railway, Fly.io, Render, AWS ECS, self-hosted VPS
   - Requires Postgres + Redis

3. **Database:**
   - PostgreSQL: Neon, Supabase, RDS, Railway
   - Redis: Upstash, Redis Cloud, Railway

See `AGENTS.md` "Deployment Considerations" section for details.

## Contributing

See `/AGENTS.md` (project root) for code style guidelines.

## License

MIT-Apache (see project root)

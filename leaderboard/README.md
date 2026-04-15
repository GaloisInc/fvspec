# fvspec Leaderboard

Public-facing dataset explorer for the fvspec formal verification benchmark.

## Quick Start

```bash
cp .env.example .env
npm install
npm run dev     # Web (port 3000) + standalone API (port 3001)
```

Open http://localhost:3000.

## Architecture

Single Next.js package with an embedded Hono API. No database — dataset loaded from JSONL/S3 at startup.

- `src/` — Next.js app (pages, components, lib)
- `src/lib/api.ts` — Hono API (mounted at `/api` via Next.js route handler)
- `server/index.ts` — Standalone Hono server for local dev

See `AGENTS.md` for detailed documentation.

## Commands

```bash
npm run dev          # Run web + standalone API in parallel
npm run dev:web      # Next.js dev server only
npm run dev:api      # Standalone API server only
npm run build        # Build Next.js
npm run lint         # Lint
npm run typecheck    # Type-check
```

## Deployment

Deploys as a standard Next.js app. The API is embedded — no separate server process needed.

**Production:** https://fvspec-benchmark.galois.com

## Contributing

See root `AGENTS.md` for code style guidelines.

## License

MIT-Apache (see project root)

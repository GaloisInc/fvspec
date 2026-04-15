import { Hono } from 'hono'
import type { DatasetSampleListItem, DatasetStats } from './schemas/dataset'

const app = new Hono().basePath('/api')

// Pre-computed data loaded from build-time JSON files
let statsCache: DatasetStats | null = null
let listCache: DatasetSampleListItem[] | null = null
let dataDir: string | null = null

async function loadPrecomputedData(): Promise<void> {
  if (statsCache && listCache) return

  const fs = await import('node:fs')
  const path = await import('node:path')

  dataDir = path.resolve(process.cwd(), 'data')
  const statsPath = path.join(dataDir, 'stats.json')
  const listPath = path.join(dataDir, 'list.json')

  if (!fs.existsSync(statsPath) || !fs.existsSync(listPath)) {
    throw new Error('Pre-computed data not found. Run `tsx scripts/precompute-dataset.ts` first.')
  }

  statsCache = JSON.parse(fs.readFileSync(statsPath, 'utf-8'))
  listCache = JSON.parse(fs.readFileSync(listPath, 'utf-8'))
  console.log(`[api] Loaded pre-computed stats and list (${listCache!.length} samples)`)
}

// Health check
app.get('/', c => c.json({ ok: true, service: 'fvspec-leaderboard-api' }))

/**
 * GET /api/dataset/stats
 * Returns aggregate statistics for the entire dataset (pre-computed at build time)
 */
app.get('/dataset/stats', async c => {
  try {
    await loadPrecomputedData()
    return c.json(statsCache)
  } catch (error) {
    console.error('GET /api/dataset/stats error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load statistics' }, 500)
  }
})

/**
 * GET /api/dataset/list
 * Returns paginated list of dataset samples with optional search (pre-computed at build time).
 *
 * Query params:
 *   q     - substring search on sample_name (case-insensitive)
 *   page  - 1-indexed page number (default 1)
 *   limit - results per page (default 50, max 200)
 */
app.get('/dataset/list', async c => {
  try {
    await loadPrecomputedData()

    const q = c.req.query('q') || undefined
    const page = Math.max(1, parseInt(c.req.query('page') || '1', 10) || 1)
    const limit = Math.min(200, Math.max(1, parseInt(c.req.query('limit') || '50', 10) || 50))

    const all = listCache!
    const filtered = q
      ? all.filter(s => s.sample_name.toLowerCase().includes(q.toLowerCase()))
      : all

    const total = filtered.length
    const start = (page - 1) * limit
    const samples = filtered.slice(start, start + limit)

    return c.json({ samples, total, page, limit })
  } catch (error) {
    console.error('GET /api/dataset/list error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load dataset' }, 500)
  }
})

/**
 * GET /api/dataset/:id
 * Returns full sample by ID from pre-computed individual sample files.
 */
app.get('/dataset/:id', async c => {
  try {
    await loadPrecomputedData()

    const idParam = c.req.param('id')
    const id = parseInt(idParam, 10)

    if (isNaN(id)) {
      return c.json({ error: 'Invalid sample ID' }, 400)
    }

    const fs = await import('node:fs')
    const path = await import('node:path')
    const samplePath = path.join(dataDir!, 'samples', `${id}.json`)

    if (!fs.existsSync(samplePath)) {
      return c.json({ error: 'Sample not found' }, 404)
    }

    const sample = JSON.parse(fs.readFileSync(samplePath, 'utf-8'))
    return c.json(sample)
  } catch (error) {
    console.error('GET /api/dataset/:id error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load sample' }, 500)
  }
})

export default app

import { Hono } from 'hono'
import {
  loadDataset,
  loadDatasetFromUrl,
  searchSamples,
  getSampleById,
  getDatasetStats,
} from './dataset'

const app = new Hono().basePath('/api')

// Dataset loading: DATASET_PATH (local file) > DATASET_URL (remote) > S3 default
const DATASET_URL_DEFAULT = 'https://fvspec-vercel-assets.s3.us-west-2.amazonaws.com/fvspec.jsonl'

let datasetInitPromise: Promise<void> | null = null

function ensureDataset(): Promise<void> {
  if (!datasetInitPromise) {
    datasetInitPromise = (async () => {
      try {
        if (process.env.DATASET_PATH) {
          await loadDataset(process.env.DATASET_PATH)
        } else {
          const url = process.env.DATASET_URL || DATASET_URL_DEFAULT
          await loadDatasetFromUrl(url)
        }
        console.log('[api] Dataset loaded successfully')
      } catch (error) {
        console.error('[api] Failed to load dataset:', error)
        datasetInitPromise = null
        throw error
      }
    })()
  }
  return datasetInitPromise
}

// Ensure dataset is loaded before handling requests
app.use('*', async (_c, next) => {
  await ensureDataset()
  await next()
})

// Health check
app.get('/', c => c.json({ ok: true, service: 'fvspec-leaderboard-api' }))

/**
 * GET /api/dataset/list
 * Returns paginated list of dataset samples with optional search.
 *
 * Query params:
 *   q     - substring search on sample_name (case-insensitive)
 *   page  - 1-indexed page number (default 1)
 *   limit - results per page (default 50, max 200)
 */
app.get('/dataset/list', c => {
  try {
    const q = c.req.query('q') || undefined
    const page = Math.max(1, parseInt(c.req.query('page') || '1', 10) || 1)
    const limit = Math.min(200, Math.max(1, parseInt(c.req.query('limit') || '50', 10) || 50))

    const result = searchSamples(q, page, limit)
    return c.json(result)
  } catch (error) {
    console.error('GET /api/dataset/list error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load dataset' }, 500)
  }
})

/**
 * GET /api/dataset/stats
 * Returns aggregate statistics for the entire dataset
 */
app.get('/dataset/stats', c => {
  try {
    const stats = getDatasetStats()
    return c.json(stats)
  } catch (error) {
    console.error('GET /api/dataset/stats error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to calculate statistics' }, 500)
  }
})

/**
 * GET /api/dataset/:id
 * Returns full sample by ID
 */
app.get('/dataset/:id', c => {
  try {
    const idParam = c.req.param('id')
    const id = parseInt(idParam, 10)

    if (isNaN(id)) {
      return c.json({ error: 'Invalid sample ID' }, 400)
    }

    const sample = getSampleById(id)

    if (!sample) {
      return c.json({ error: 'Sample not found' }, 404)
    }

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

import 'dotenv/config'
import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { logger } from 'hono/logger'
import { serve } from '@hono/node-server'
import path from 'node:path'
import { loadDataset, getAllSamples, getSampleById, getDatasetStats } from './lib/dataset.js'

const app = new Hono()

// Middleware
app.use('*', logger())
app.use(
  '*',
  cors({
    origin: '*',
    allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowHeaders: ['Content-Type', 'Authorization'],
    exposeHeaders: ['Content-Length'],
    credentials: false,
  })
)

// Handle preflight requests for Private Network Access
// Required when public sites (https://fvspec-benchmark.galois.com) access localhost
app.options('*', c => {
  c.header('Access-Control-Allow-Private-Network', 'true')
  return c.body(null, 204)
})

// Load dataset at startup
// Use environment variable or default relative path
const datasetPath =
  process.env.DATASET_PATH ||
  path.resolve(process.cwd(), '../../../benchmark/artifacts/dataset-out/fvspec.jsonl')
try {
  loadDataset(datasetPath)
  console.log('[startup] Dataset loaded successfully')
} catch (error) {
  console.error('[startup] Failed to load dataset:', error)
  console.error('[startup] Dataset endpoints will not be available')
}

// Health check
app.get('/', c => c.json({ ok: true, service: 'fvspec-leaderboard-api' }))

/**
 * GET /dataset/list
 * Returns list of all dataset samples (minimal data for dropdown)
 */
app.get('/dataset/list', c => {
  try {
    const samples = getAllSamples()
    return c.json({ samples, total: samples.length })
  } catch (error) {
    console.error('GET /dataset/list error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load dataset' }, 500)
  }
})

/**
 * GET /dataset/stats
 * Returns aggregate statistics for the entire dataset
 * IMPORTANT: Must come before /dataset/:id to avoid being matched as an ID
 */
app.get('/dataset/stats', c => {
  try {
    const stats = getDatasetStats()
    return c.json(stats)
  } catch (error) {
    console.error('GET /dataset/stats error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to calculate statistics' }, 500)
  }
})

/**
 * GET /dataset/:id
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
    console.error('GET /dataset/:id error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 500)
    }
    return c.json({ error: 'Failed to load sample' }, 500)
  }
})

// Start server
const port = Number(process.env.PORT) || 3001

serve(
  {
    fetch: app.fetch,
    port,
  },
  info => {
    console.log(`API listening on http://localhost:${info.port}`)
  }
)

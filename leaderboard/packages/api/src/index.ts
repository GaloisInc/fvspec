import 'dotenv/config'
import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { logger } from 'hono/logger'
import { serve } from '@hono/node-server'
import { eq, desc, sql, and } from 'drizzle-orm'
import path from 'node:path'
import {
  CreateSubmissionSchema,
  ResultsRequestSchema,
  LeaderboardQuerySchema,
  type LeaderboardEntry,
  type RunDetail,
  type Attestation,
} from '@fvspec/common'
import { db } from './db/client.js'
import { submissions, runs, results, attestations } from './db/schema.js'
import { submissionsQueue } from './lib/queue.js'
import { requireApiToken } from './lib/auth.js'
import { loadDataset, getAllSamples, getSampleById } from './lib/dataset.js'

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
 * POST /submit
 * Accept new submission, create DB records, enqueue job
 */
app.post('/submit', async c => {
  try {
    const body: unknown = await c.req.json()
    const data = CreateSubmissionSchema.parse(body)

    // Insert submission record
    const [submission] = await db
      .insert(submissions)
      .values({
        repoUrl: data.repoUrl,
        commitSha: data.commitSha,
        trackId: data.trackId,
        payload: data.payload || null,
        model: null,
        organization: null,
      })
      .returning()

    // Create initial run record
    const [run] = await db
      .insert(runs)
      .values({
        submissionId: submission.id,
        status: 'pending',
      })
      .returning()

    // Enqueue job for worker
    await submissionsQueue.add(
      'run',
      {
        submissionId: submission.id,
        runId: run.id,
        repoUrl: data.repoUrl,
        commitSha: data.commitSha,
        trackId: data.trackId,
      },
      {
        attempts: 3,
        backoff: { type: 'exponential', delay: 5000 },
      }
    )

    return c.json({ ok: true, submissionId: submission.id, runId: run.id })
  } catch (error) {
    console.error('POST /submit error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 400)
    }
    return c.json({ error: 'Invalid request' }, 400)
  }
})

/**
 * POST /results
 * Internal endpoint for worker to report results
 * Requires API token authentication
 */
app.post('/results', requireApiToken, async c => {
  try {
    const body: unknown = await c.req.json()
    const data = ResultsRequestSchema.parse(body)

    // Find the run record
    const [run] = await db
      .select()
      .from(runs)
      .where(eq(runs.submissionId, data.submissionId))
      .orderBy(desc(runs.createdAt))
      .limit(1)

    if (!run) {
      return c.json({ error: 'Run not found' }, 404)
    }

    // Update run status
    await db
      .update(runs)
      .set({
        status: data.status,
        finishedAt: new Date(),
        logPath: data.logs?.logPath || null,
        errorMessage: data.errorMessage || null,
        updatedAt: new Date(),
      })
      .where(eq(runs.id, run.id))

    // If succeeded, insert result and attestation
    if (data.status === 'succeeded' && data.metrics.score !== null) {
      await db.insert(results).values({
        runId: run.id,
        submissionId: data.submissionId,
        score: data.metrics.score.toString(),
        passRate: data.metrics.passRate || '0/0',
        avgTime: data.metrics.avgTime || '0s',
        metrics: null,
      })

      if (data.attestation) {
        await db.insert(attestations).values({
          runId: run.id,
          submissionId: data.submissionId,
          attestation: data.attestation,
        })
      }
    }

    return c.json({ ok: true })
  } catch (error) {
    console.error('POST /results error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 400)
    }
    return c.json({ error: 'Invalid request' }, 400)
  }
})

/**
 * GET /leaderboard
 * Query ranked submissions with optional filtering
 */
app.get('/leaderboard', async c => {
  try {
    const query = LeaderboardQuerySchema.parse({
      track: c.req.query('track'),
      limit: c.req.query('limit'),
      offset: c.req.query('offset'),
    })

    // Build query with joins
    const whereConditions = []
    if (query.track) {
      whereConditions.push(eq(submissions.trackId, query.track))
    }
    whereConditions.push(eq(runs.status, 'succeeded'))

    // Get total count
    const [{ count }] = await db
      .select({ count: sql<number>`count(*)` })
      .from(submissions)
      .innerJoin(runs, eq(runs.submissionId, submissions.id))
      .innerJoin(results, eq(results.runId, runs.id))
      .where(whereConditions.length > 0 ? and(...whereConditions) : undefined)

    // Get entries with ranking
    const rawEntries = await db
      .select({
        id: submissions.id,
        repoUrl: submissions.repoUrl,
        commitSha: submissions.commitSha,
        trackId: submissions.trackId,
        model: submissions.model,
        organization: submissions.organization,
        createdAt: submissions.createdAt,
        runStatus: runs.status,
        score: results.score,
        passRate: results.passRate,
        avgTime: results.avgTime,
      })
      .from(submissions)
      .innerJoin(runs, eq(runs.submissionId, submissions.id))
      .innerJoin(results, eq(results.runId, runs.id))
      .where(whereConditions.length > 0 ? and(...whereConditions) : undefined)
      .orderBy(desc(results.score), desc(submissions.createdAt))
      .limit(query.limit)
      .offset(query.offset)

    // Add ranking
    const entries: LeaderboardEntry[] = rawEntries.map((entry, index) => ({
      id: entry.id,
      rank: query.offset + index + 1,
      model: entry.model || 'Unknown',
      organization: entry.organization || 'Unknown',
      track: entry.trackId,
      score: Number(entry.score),
      passRate: entry.passRate,
      avgTime: entry.avgTime,
      status: entry.runStatus,
      date: entry.createdAt.toISOString(),
      commitSha: entry.commitSha,
      repoUrl: entry.repoUrl,
    }))

    return c.json({ entries, total: Number(count) })
  } catch (error) {
    console.error('GET /leaderboard error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 400)
    }
    return c.json({ error: 'Invalid request' }, 400)
  }
})

/**
 * GET /runs/:id
 * Fetch detailed status and results for a specific run
 */
app.get('/runs/:id', async c => {
  try {
    const runId = parseInt(c.req.param('id'), 10)

    if (isNaN(runId)) {
      return c.json({ error: 'Invalid run ID' }, 400)
    }

    // Get run with optional result and attestation
    const [run] = await db.select().from(runs).where(eq(runs.id, runId)).limit(1)

    if (!run) {
      return c.json({ error: 'Run not found' }, 404)
    }

    // Get result if exists
    const [result] = await db.select().from(results).where(eq(results.runId, runId)).limit(1)

    // Get attestation if exists
    const [attestation] = await db
      .select()
      .from(attestations)
      .where(eq(attestations.runId, runId))
      .limit(1)

    const response: RunDetail = {
      id: run.id,
      submissionId: run.submissionId,
      status: run.status,
      startedAt: run.startedAt?.toISOString() || null,
      finishedAt: run.finishedAt?.toISOString() || null,
      errorMessage: run.errorMessage,
      result: result
        ? {
            score: Number(result.score),
            passRate: result.passRate,
            avgTime: result.avgTime,
            metrics: result.metrics as Record<string, unknown> | null,
          }
        : null,
      attestation: attestation ? (attestation.attestation as Attestation) : null,
    }

    return c.json(response)
  } catch (error) {
    console.error('GET /runs/:id error:', error)
    if (error instanceof Error) {
      return c.json({ error: error.message }, 400)
    }
    return c.json({ error: 'Internal server error' }, 500)
  }
})

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

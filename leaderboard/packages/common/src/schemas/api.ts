import { z } from 'zod'
import { CreateSubmissionSchema } from './submission.js'
import { AttestationSchema } from './attestation.js'

/**
 * POST /submit request
 */
export const SubmitRequestSchema = CreateSubmissionSchema

export type SubmitRequest = z.infer<typeof SubmitRequestSchema>

/**
 * POST /submit response
 */
export const SubmitResponseSchema = z.object({
  ok: z.boolean(),
  submissionId: z.number(),
})

export type SubmitResponse = z.infer<typeof SubmitResponseSchema>

/**
 * GET /leaderboard query params
 */
export const LeaderboardQuerySchema = z.object({
  track: z.string().optional(),
  limit: z.coerce.number().int().positive().max(100).default(50),
  offset: z.coerce.number().int().nonnegative().default(0),
})

export type LeaderboardQuery = z.infer<typeof LeaderboardQuerySchema>

/**
 * Leaderboard entry (joined submission + result)
 */
export const LeaderboardEntrySchema = z.object({
  id: z.number(),
  rank: z.number(),
  model: z.string(),
  organization: z.string(),
  track: z.string(),
  score: z.number(),
  passRate: z.string(),
  avgTime: z.string(),
  status: z.string(),
  date: z.string(),
  commitSha: z.string(),
  repoUrl: z.string(),
})

export type LeaderboardEntry = z.infer<typeof LeaderboardEntrySchema>

/**
 * GET /leaderboard response
 */
export const LeaderboardResponseSchema = z.object({
  entries: z.array(LeaderboardEntrySchema),
  total: z.number(),
})

export type LeaderboardResponse = z.infer<typeof LeaderboardResponseSchema>

/**
 * GET /runs/:id response
 */
export const RunDetailSchema = z.object({
  id: z.number(),
  submissionId: z.number(),
  status: z.string(),
  startedAt: z.string().nullable(),
  finishedAt: z.string().nullable(),
  errorMessage: z.string().nullable(),
  result: z
    .object({
      score: z.number(),
      passRate: z.string(),
      avgTime: z.string(),
      metrics: z.record(z.string(), z.unknown()).nullable(),
    })
    .nullable(),
  attestation: AttestationSchema.nullable(),
})

export type RunDetail = z.infer<typeof RunDetailSchema>

/**
 * POST /ingest request (worker -> API)
 */
export const IngestRequestSchema = z.object({
  submissionId: z.number(),
  status: z.enum(['succeeded', 'failed']),
  metrics: z.object({
    score: z.number().nullable(),
    passRate: z.string().nullable(),
    avgTime: z.string().nullable(),
  }),
  attestation: AttestationSchema.optional(),
  logs: z
    .object({
      logPath: z.string(),
    })
    .optional(),
  errorMessage: z.string().optional(),
})

export type IngestRequest = z.infer<typeof IngestRequestSchema>

/**
 * POST /ingest response
 */
export const IngestResponseSchema = z.object({
  ok: z.boolean(),
})

export type IngestResponse = z.infer<typeof IngestResponseSchema>

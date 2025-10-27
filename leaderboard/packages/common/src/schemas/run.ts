import { z } from 'zod'
import { RUN_STATUS } from '../constants.js'

/**
 * Run/Job execution record
 */
export const RunSchema = z.object({
  id: z.number(),
  submissionId: z.number(),
  status: z.enum([
    RUN_STATUS.PENDING,
    RUN_STATUS.RUNNING,
    RUN_STATUS.SUCCEEDED,
    RUN_STATUS.FAILED,
    RUN_STATUS.CANCELLED,
  ]),
  startedAt: z.string().datetime().nullable(),
  finishedAt: z.string().datetime().nullable(),
  logPath: z.string().nullable(),
  errorMessage: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
})

export type Run = z.infer<typeof RunSchema>

/**
 * Result metrics
 */
export const ResultSchema = z.object({
  id: z.number(),
  runId: z.number(),
  submissionId: z.number(),
  score: z.number(), // Percentage 0-100
  passRate: z.string(), // e.g., "175/200"
  avgTime: z.string(), // e.g., "45s"
  metrics: z.record(z.string(), z.unknown()).nullable(), // Additional structured metrics
  createdAt: z.string().datetime(),
})

export type Result = z.infer<typeof ResultSchema>

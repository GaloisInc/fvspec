import { z } from 'zod'
import type { Track } from '@fvspec/common'

/**
 * Job data for BullMQ queue
 * This is what gets pushed to the queue by the API
 */
export const SubmissionJob = z.object({
  submissionId: z.number(),
  runId: z.number(),
  repoUrl: z.string().url(),
  commitSha: z.string().min(7),
  trackId: z.string() as z.ZodType<Track>,
  payload: z.record(z.string(), z.unknown()).optional(),
})

export type SubmissionJob = z.infer<typeof SubmissionJob>

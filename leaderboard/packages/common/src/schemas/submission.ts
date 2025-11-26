import { z } from 'zod'
import { TRACKS } from '../constants.js'

/**
 * Schema for creating a new submission
 */
export const CreateSubmissionSchema = z.object({
  repoUrl: z.string().url(),
  commitSha: z.string().min(7).max(40),
  trackId: z.enum([TRACKS.FUNCTIONAL, TRACKS.MVCGEN]),
  payload: z.record(z.string(), z.unknown()).optional(),
})

export type CreateSubmission = z.infer<typeof CreateSubmissionSchema>

/**
 * Full submission record (from database)
 */
export const SubmissionSchema = z.object({
  id: z.number(),
  repoUrl: z.string(),
  commitSha: z.string(),
  trackId: z.string(),
  model: z.string().nullable(),
  organization: z.string().nullable(),
  payload: z.record(z.string(), z.unknown()).nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
})

export type Submission = z.infer<typeof SubmissionSchema>

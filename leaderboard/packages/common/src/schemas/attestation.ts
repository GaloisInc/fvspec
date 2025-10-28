import { z } from 'zod'
import { RUNNER_TRUST, TRACKS } from '../constants.js'

/**
 * Artifact with SHA-256 hash
 */
export const ArtifactSchema = z.object({
  path: z.string(),
  sha256: z.string(),
})

export type Artifact = z.infer<typeof ArtifactSchema>

/**
 * Toolchain information
 */
export const ToolchainSchema = z.object({
  imageDigest: z.string().optional(),
  lean: z.string().optional(),
  lake: z.string().optional(),
})

export type Toolchain = z.infer<typeof ToolchainSchema>

/**
 * Runner information
 */
export const RunnerSchema = z.object({
  name: z.string(),
  trust: z.enum([RUNNER_TRUST.INTERNAL, RUNNER_TRUST.PARTNER, RUNNER_TRUST.COMMUNITY]),
})

export type Runner = z.infer<typeof RunnerSchema>

/**
 * Resource limits
 */
export const LimitsSchema = z.object({
  timeSec: z.number(),
  memoryMB: z.number(),
})

export type Limits = z.infer<typeof LimitsSchema>

/**
 * Full attestation object
 */
export const AttestationSchema = z.object({
  schema: z.string().url(),
  submissionId: z.number(),
  repoUrl: z.string().url(),
  commitSha: z.string(),
  trackId: z.enum([TRACKS.FUNCTIONAL, TRACKS.MVCGEN]),
  toolchain: ToolchainSchema.optional(),
  runner: RunnerSchema,
  startedAt: z.string().datetime(),
  finishedAt: z.string().datetime(),
  artifacts: z.array(ArtifactSchema),
  limits: LimitsSchema,
})

export type Attestation = z.infer<typeof AttestationSchema>

/**
 * Database record for attestation
 */
export const AttestationRecordSchema = z.object({
  id: z.number(),
  runId: z.number(),
  submissionId: z.number(),
  attestation: AttestationSchema,
  createdAt: z.string().datetime(),
})

export type AttestationRecord = z.infer<typeof AttestationRecordSchema>

/**
 * Verification tracks
 */
export const TRACKS = {
  FUNCTIONAL: 'functional',
  MVCGEN: 'mvcgen',
} as const

export type Track = (typeof TRACKS)[keyof typeof TRACKS]

/**
 * Job/Run status values
 */
export const RUN_STATUS = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCEEDED: 'succeeded',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const

export type RunStatus = (typeof RUN_STATUS)[keyof typeof RUN_STATUS]

/**
 * Runner trust levels
 */
export const RUNNER_TRUST = {
  INTERNAL: 'internal',
  PARTNER: 'partner',
  COMMUNITY: 'community',
} as const

export type RunnerTrust = (typeof RUNNER_TRUST)[keyof typeof RUNNER_TRUST]

/**
 * Benchmark constants
 */
export const BENCHMARK_SIZE = 200
export const DEFAULT_TIME_LIMIT_SEC = 7200 // 2 hours
export const DEFAULT_MEMORY_MB = 16000 // 16 GB

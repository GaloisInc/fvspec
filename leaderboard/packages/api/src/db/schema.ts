import { pgTable, serial, text, timestamp, integer, jsonb, numeric } from 'drizzle-orm/pg-core'

/**
 * Submissions table
 * Stores user-submitted benchmark runs
 */
export const submissions = pgTable('submissions', {
  id: serial('id').primaryKey(),
  repoUrl: text('repo_url').notNull(),
  commitSha: text('commit_sha').notNull(),
  trackId: text('track_id').notNull(), // 'functional' | 'mvcgen'
  model: text('model'),
  organization: text('organization'),
  payload: jsonb('payload'), // Additional metadata
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
})

/**
 * Runs table
 * Tracks execution status of each submission
 */
export const runs = pgTable('runs', {
  id: serial('id').primaryKey(),
  submissionId: integer('submission_id')
    .notNull()
    .references(() => submissions.id, { onDelete: 'cascade' }),
  status: text('status').notNull().default('pending'), // 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  startedAt: timestamp('started_at'),
  finishedAt: timestamp('finished_at'),
  logPath: text('log_path'),
  errorMessage: text('error_message'),
  createdAt: timestamp('created_at').notNull().defaultNow(),
  updatedAt: timestamp('updated_at').notNull().defaultNow(),
})

/**
 * Results table
 * Stores metrics from successful builds
 */
export const results = pgTable('results', {
  id: serial('id').primaryKey(),
  runId: integer('run_id')
    .notNull()
    .references(() => runs.id, { onDelete: 'cascade' }),
  submissionId: integer('submission_id')
    .notNull()
    .references(() => submissions.id, { onDelete: 'cascade' }),
  score: numeric('score', { precision: 5, scale: 2 }).notNull(), // 0-100 percentage
  passRate: text('pass_rate').notNull(), // e.g., "175/200"
  avgTime: text('avg_time').notNull(), // e.g., "45s"
  metrics: jsonb('metrics'), // Additional structured metrics
  createdAt: timestamp('created_at').notNull().defaultNow(),
})

/**
 * Attestations table
 * Stores cryptographic attestations for reproducibility
 */
export const attestations = pgTable('attestations', {
  id: serial('id').primaryKey(),
  runId: integer('run_id')
    .notNull()
    .references(() => runs.id, { onDelete: 'cascade' }),
  submissionId: integer('submission_id')
    .notNull()
    .references(() => submissions.id, { onDelete: 'cascade' }),
  attestation: jsonb('attestation').notNull(), // Full attestation object
  createdAt: timestamp('created_at').notNull().defaultNow(),
})

// Type exports for use in application code
export type Submission = typeof submissions.$inferSelect
export type NewSubmission = typeof submissions.$inferInsert
export type Run = typeof runs.$inferSelect
export type NewRun = typeof runs.$inferInsert
export type Result = typeof results.$inferSelect
export type NewResult = typeof results.$inferInsert
export type Attestation = typeof attestations.$inferSelect
export type NewAttestation = typeof attestations.$inferInsert

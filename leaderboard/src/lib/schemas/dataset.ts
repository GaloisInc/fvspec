import { z } from 'zod'

/**
 * Minimal dataset sample for list view (dropdown).
 * Contains only identifiers needed for sample selection.
 */
export const DifficultyBinarySchema = z.enum(['easy', 'hard'])
export type DifficultyBinary = z.infer<typeof DifficultyBinarySchema>

export const DatasetSampleListItemSchema = z.object({
  sample_id: z.number(),
  sample_name: z.string(),
  difficulty_binary: DifficultyBinarySchema.nullable().optional(),
})

/**
 * Lean code structure metrics (lines, counts).
 */
const LeanStructureSchema = z
  .object({
    total_lines: z.number(),
    code_lines: z.number(),
    num_theorems: z.number(),
    num_sorries: z.number(),
  })
  .passthrough()

/**
 * Lean metrics for spec, impl, and tests.
 */
const LeanMetricsSchema = z
  .object({
    spec_structure: LeanStructureSchema.nullable().optional(),
    impl_structure: LeanStructureSchema.nullable().optional(),
    tests_structure: LeanStructureSchema.nullable().optional(),
    total_lean_lines: z.number().optional(),
    total_sorries: z.number().optional(),
  })
  .passthrough()

/**
 * Full dataset sample with all code and metadata.
 * Used for detailed sample view.
 */
export const DatasetSampleDetailSchema = z.object({
  // Identifiers
  sample_id: z.number(),
  sample_name: z.string(),

  // Code content (Lean)
  spec: z.string(),
  impl: z.string(),

  // Original PBT source
  realpbt_code: z.string().optional(),
  realpbt_summary: z.string().nullable().optional(),
  realpbt_repo_id: z.number().optional(),
  realpbt_lines_pbt: z.number().nullable().optional(),
  realpbt_sample_name: z.string().optional(),

  // Metrics
  num_theorems: z.number().optional(),
  lean_metrics: LeanMetricsSchema.nullable().optional(),
  structural_faithfulness: z.record(z.string(), z.unknown()).nullable().optional(),
  difficulty_binary: DifficultyBinarySchema.nullable().optional(),
  difficulty_binary_confidence: z.number().nullable().optional(),
  difficulty_binary_reasoning: z.string().nullable().optional(),
})

/**
 * Response wrapper for dataset list endpoint.
 * Includes pagination metadata for server-side pagination.
 */
export const DatasetListResponseSchema = z.object({
  samples: z.array(DatasetSampleListItemSchema),
  total: z.number(),
  page: z.number(),
  limit: z.number(),
})

/**
 * Distribution statistics for a metric.
 */
export const DistributionStatsSchema = z.object({
  mean: z.number().nullable(),
  median: z.number().nullable(),
  q1: z.number().nullable(),
  q3: z.number().nullable(),
  min: z.number().nullable(),
  max: z.number().nullable(),
})

/**
 * Aggregate statistics for the entire dataset.
 */
export const DifficultyCountsSchema = z.object({
  easy: z.number(),
  hard: z.number(),
  unknown: z.number(),
})

export const DatasetStatsSchema = z.object({
  total: z.number(),
  faithfulness: DistributionStatsSchema,
  theorems: DistributionStatsSchema,
  lean_lines: DistributionStatsSchema,
  difficulty: DifficultyCountsSchema,
})

// Export TypeScript types
export type DatasetSampleListItem = z.infer<typeof DatasetSampleListItemSchema>
export type DatasetSampleDetail = z.infer<typeof DatasetSampleDetailSchema>
export type DatasetListResponse = z.infer<typeof DatasetListResponseSchema>
export type DistributionStats = z.infer<typeof DistributionStatsSchema>
export type DifficultyCounts = z.infer<typeof DifficultyCountsSchema>
export type DatasetStats = z.infer<typeof DatasetStatsSchema>

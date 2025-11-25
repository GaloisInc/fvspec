import { z } from 'zod'

/**
 * Minimal dataset sample for list view (dropdown).
 * Contains only identifiers needed for sample selection.
 */
export const DatasetSampleListItemSchema = z.object({
  sample_id: z.number(),
  sample_name: z.string(),
})

/**
 * Full dataset sample with all code and metadata.
 * Used for detailed sample view.
 */
export const DatasetSampleDetailSchema = z.object({
  // Identifiers
  sample_id: z.number(),
  sample_name: z.string(),

  // Code content
  code: z.string(), // Python PBT source
  spec: z.string(), // Generated Lean spec
  impl: z.string(), // Generated Lean impl
  tests: z.string(), // Generated Lean tests

  // Metadata
  summary: z.string().nullable().optional(), // Can be null or missing
  repo_id: z.number().optional(), // Number, not string
  source_file: z.string().optional(),
  variant: z.string().optional(),
  model: z.string().optional(),
  datetime: z.string().optional(),

  // Metrics
  lines_pbt: z.number().optional(),
  lines_code: z.number().optional(),
  num_theorems: z.number().optional(),
  structural_faithfulness: z.record(z.string(), z.unknown()).nullable().optional(),
})

/**
 * Response wrapper for dataset list endpoint.
 */
export const DatasetListResponseSchema = z.object({
  samples: z.array(DatasetSampleListItemSchema),
  total: z.number(),
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
export const DatasetStatsSchema = z.object({
  total: z.number(),
  faithfulness: DistributionStatsSchema,
  theorems: DistributionStatsSchema,
  lines_pbt: DistributionStatsSchema,
  lines_code: DistributionStatsSchema,
  by_variant: z.record(z.string(), z.number()),
  by_model: z.record(z.string(), z.number()),
  by_repo: z.array(z.object({ key: z.string(), count: z.number() })),
})

// Export TypeScript types
export type DatasetSampleListItem = z.infer<typeof DatasetSampleListItemSchema>
export type DatasetSampleDetail = z.infer<typeof DatasetSampleDetailSchema>
export type DatasetListResponse = z.infer<typeof DatasetListResponseSchema>
export type DistributionStats = z.infer<typeof DistributionStatsSchema>
export type DatasetStats = z.infer<typeof DatasetStatsSchema>

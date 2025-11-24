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
  summary: z.string().optional(),
  repo_id: z.string().optional(),
  source_file: z.string().optional(),
  variant: z.string().optional(),
  model: z.string().optional(),
  datetime: z.string().optional(),

  // Metrics
  lines_pbt: z.number().optional(),
  lines_code: z.number().optional(),
  num_theorems: z.number().optional(),
  structural_faithfulness: z.record(z.string(), z.unknown()).optional(),
})

/**
 * Response wrapper for dataset list endpoint.
 */
export const DatasetListResponseSchema = z.object({
  samples: z.array(DatasetSampleListItemSchema),
  total: z.number(),
})

// Export TypeScript types
export type DatasetSampleListItem = z.infer<typeof DatasetSampleListItemSchema>
export type DatasetSampleDetail = z.infer<typeof DatasetSampleDetailSchema>
export type DatasetListResponse = z.infer<typeof DatasetListResponseSchema>

import fs from 'node:fs'
import {
  DatasetSampleDetail,
  DatasetSampleListItem,
  DatasetSampleDetailSchema,
  DatasetStats,
} from '@fvspec/common'
import { calculateDistribution, countByValue, getTopEntries } from './stats.js'

/**
 * In-memory cache of dataset samples.
 * Key: sample_id, Value: full sample data
 */
let datasetCache: Map<number, DatasetSampleDetail> | null = null

/**
 * Cached sorted list of all samples for efficient retrieval.
 * Populated once during loadDataset() to avoid recreating on every getAllSamples() call.
 */
let sampleListCache: DatasetSampleListItem[] | null = null

/**
 * Load dataset from JSONL file and cache in memory.
 * Should be called once at API startup.
 *
 * @param filePath - Absolute path to fvspec.jsonl file
 * @returns Map of sample_id to sample data
 * @throws Error if file not found or parse fails
 */
export function loadDataset(filePath: string): Map<number, DatasetSampleDetail> {
  try {
    console.log(`[dataset] Loading dataset from ${filePath}...`)

    if (!fs.existsSync(filePath)) {
      throw new Error(`Dataset file not found: ${filePath}`)
    }

    const fileContent = fs.readFileSync(filePath, 'utf-8')
    const lines = fileContent.split('\n').filter(line => line.trim().length > 0)

    const cache = new Map<number, DatasetSampleDetail>()

    for (let i = 0; i < lines.length; i++) {
      try {
        // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
        const sample = JSON.parse(lines[i])

        // Validate using Zod schema

        const parseResult = DatasetSampleDetailSchema.safeParse(sample)

        if (!parseResult.success) {
          console.warn(`[dataset] Line ${i + 1}: Invalid sample data:`, parseResult.error)
          continue
        }

        // Store in cache (parseResult.data is properly typed after success check)

        const validatedSample: DatasetSampleDetail = parseResult.data

        cache.set(validatedSample.sample_id, validatedSample)
      } catch (parseError) {
        console.warn(`[dataset] Line ${i + 1}: Failed to parse JSON:`, parseError)
      }
    }

    datasetCache = cache

    // Populate sample list cache
    const samples: DatasetSampleListItem[] = []
    for (const [sampleId, sample] of cache.entries()) {
      samples.push({
        sample_id: sampleId,

        sample_name: sample.sample_name,
      })
    }

    samples.sort((a, b) => a.sample_id - b.sample_id)
    sampleListCache = samples

    console.log(`[dataset] Successfully loaded ${cache.size} samples`)

    return cache
  } catch (error) {
    console.error('[dataset] Failed to load dataset:', error)
    throw error
  }
}

/**
 * Get list of all samples (minimal data for dropdown).
 * Returns cached array sorted by sample_id.
 *
 * @returns Array of {sample_id, sample_name}
 * @throws Error if dataset not loaded
 */
export function getAllSamples(): DatasetSampleListItem[] {
  if (!datasetCache) {
    throw new Error('Dataset not loaded. Call loadDataset() first.')
  }

  // Return cached list (populated during loadDataset)
  if (sampleListCache) {
    return sampleListCache
  }

  // Fallback: build list if cache is missing (shouldn't happen in normal flow)
  const samples: DatasetSampleListItem[] = []
  for (const [sampleId, sample] of datasetCache.entries()) {
    samples.push({
      sample_id: sampleId,

      sample_name: sample.sample_name,
    })
  }

  samples.sort((a, b) => a.sample_id - b.sample_id)
  sampleListCache = samples

  return samples
}

/**
 * Get full sample by ID.
 *
 * @param id - Sample ID
 * @returns Full sample data or null if not found
 * @throws Error if dataset not loaded
 */
export function getSampleById(id: number): DatasetSampleDetail | null {
  if (!datasetCache) {
    throw new Error('Dataset not loaded. Call loadDataset() first.')
  }

  return datasetCache.get(id) ?? null
}

/**
 * Get total number of loaded samples.
 *
 * @returns Number of samples in cache
 */
export function getDatasetSize(): number {
  return datasetCache?.size ?? 0
}

/**
 * Calculate aggregate statistics across all samples.
 *
 * @returns DatasetStats object with distributions and breakdowns
 * @throws Error if dataset not loaded
 */
export function getDatasetStats(): DatasetStats {
  if (!datasetCache) {
    throw new Error('Dataset not loaded. Call loadDataset() first.')
  }

  const samples: DatasetSampleDetail[] = Array.from(datasetCache.values())

  // Extract faithfulness scores (overall score from structural_faithfulness)
  const faithfulnessScores: (number | null | undefined)[] = samples.map(
    s => s.structural_faithfulness?.overall as number | undefined
  )

  // Extract metrics

  const theorems: (number | null | undefined)[] = samples.map(s => s.num_theorems)

  const linesPbt: (number | null | undefined)[] = samples.map(s => s.lines_pbt)

  const linesCode: (number | null | undefined)[] = samples.map(s => s.lines_code)

  // Count by variant

  const variants: (string | null | undefined)[] = samples.map(s => s.variant)
  const byVariant = countByValue(variants)

  // Count by model

  const models: (string | null | undefined)[] = samples.map(s => s.model)
  const byModel = countByValue(models)

  // Count by repo (top 10)
  const repoIds: (string | null | undefined)[] = samples.map(s =>
    s.repo_id !== undefined ? String(s.repo_id) : undefined
  )
  const repoIdCounts = countByValue(repoIds)
  const byRepo = getTopEntries(repoIdCounts, 10)

  return {
    total: samples.length,
    faithfulness: calculateDistribution(faithfulnessScores),
    theorems: calculateDistribution(theorems),
    lines_pbt: calculateDistribution(linesPbt),
    lines_code: calculateDistribution(linesCode),
    by_variant: byVariant,
    by_model: byModel,
    by_repo: byRepo,
  }
}

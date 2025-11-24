import fs from 'node:fs'
import {
  DatasetSampleDetail,
  DatasetSampleListItem,
  DatasetSampleDetailSchema,
} from '@fvspec/common'

/**
 * In-memory cache of dataset samples.
 * Key: sample_id, Value: full sample data
 */
let datasetCache: Map<number, DatasetSampleDetail> | null = null

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
        const sample = JSON.parse(lines[i]) as unknown

        // Validate using Zod schema
        const parseResult = DatasetSampleDetailSchema.safeParse(sample)
        if (!parseResult.success) {
          console.warn(`[dataset] Line ${i + 1}: Invalid sample data:`, parseResult.error)
          continue
        }

        // Store in cache
        cache.set(parseResult.data.sample_id, parseResult.data)
      } catch (parseError) {
        console.warn(`[dataset] Line ${i + 1}: Failed to parse JSON:`, parseError)
      }
    }

    datasetCache = cache
    console.log(`[dataset] Successfully loaded ${cache.size} samples`)

    return cache
  } catch (error) {
    console.error('[dataset] Failed to load dataset:', error)
    throw error
  }
}

/**
 * Get list of all samples (minimal data for dropdown).
 * Returns array sorted by sample_id.
 *
 * @returns Array of {sample_id, sample_name}
 * @throws Error if dataset not loaded
 */
export function getAllSamples(): DatasetSampleListItem[] {
  if (!datasetCache) {
    throw new Error('Dataset not loaded. Call loadDataset() first.')
  }

  const samples: DatasetSampleListItem[] = []

  for (const [sampleId, sample] of datasetCache.entries()) {
    samples.push({
      sample_id: sampleId,
      sample_name: sample.sample_name,
    })
  }

  // Sort by sample_id for consistent ordering
  samples.sort((a, b) => a.sample_id - b.sample_id)

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

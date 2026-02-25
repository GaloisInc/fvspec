import {
  DatasetSampleDetail,
  DatasetSampleListItem,
  DatasetSampleDetailSchema,
  DatasetStats,
} from '@fvspec/common'
import { calculateDistribution, countByValue, getTopEntries } from './stats'

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
 * Parse JSONL content into the dataset cache.
 */
function parseDataset(content: string): Map<number, DatasetSampleDetail> {
  const lines = content.split('\n').filter(line => line.trim().length > 0)
  const cache = new Map<number, DatasetSampleDetail>()

  for (let i = 0; i < lines.length; i++) {
    try {
      const sample = JSON.parse(lines[i])
      const parseResult = DatasetSampleDetailSchema.safeParse(sample)

      if (!parseResult.success) {
        console.warn(`[dataset] Line ${i + 1}: Invalid sample data:`, parseResult.error)
        continue
      }

      const validatedSample: DatasetSampleDetail = parseResult.data
      cache.set(validatedSample.sample_id, validatedSample)
    } catch (parseError) {
      console.warn(`[dataset] Line ${i + 1}: Failed to parse JSON:`, parseError)
    }
  }

  return cache
}

/**
 * Populate caches from a parsed dataset map.
 */
function setCaches(cache: Map<number, DatasetSampleDetail>): void {
  datasetCache = cache

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
}

/**
 * Load dataset from a local JSONL file and cache in memory.
 * Requires Node.js runtime (uses node:fs).
 */
export async function loadDataset(filePath: string): Promise<Map<number, DatasetSampleDetail>> {
  const fs = await import('node:fs')
  const path = await import('node:path')
  const resolved = path.resolve(process.cwd(), filePath)
  console.log(`[dataset] Loading dataset from ${resolved}...`)

  if (!fs.existsSync(resolved)) {
    throw new Error(`Dataset file not found: ${resolved}`)
  }

  const fileContent = fs.readFileSync(resolved, 'utf-8')
  const cache = parseDataset(fileContent)
  setCaches(cache)
  return cache
}

/**
 * Load dataset from a URL (e.g. S3) and cache in memory.
 *
 * @param url - URL to fetch fvspec.jsonl from
 * @returns Map of sample_id to sample data
 * @throws Error if fetch fails or parse fails
 */
export async function loadDatasetFromUrl(url: string): Promise<Map<number, DatasetSampleDetail>> {
  console.log(`[dataset] Fetching dataset from ${url}...`)

  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch dataset: ${response.status} ${response.statusText}`)
  }

  const content = await response.text()
  const cache = parseDataset(content)
  setCaches(cache)
  return cache
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
    throw new Error('Dataset not loaded. Call loadDatasetFromUrl() first.')
  }

  if (sampleListCache) {
    return sampleListCache
  }

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
    throw new Error('Dataset not loaded. Call loadDatasetFromUrl() first.')
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
    throw new Error('Dataset not loaded. Call loadDatasetFromUrl() first.')
  }

  const samples: DatasetSampleDetail[] = Array.from(datasetCache.values())

  const faithfulnessScores: (number | null | undefined)[] = samples.map(
    s => s.structural_faithfulness?.overall as number | undefined
  )

  const theorems: (number | null | undefined)[] = samples.map(s => s.num_theorems)
  const linesPbt: (number | null | undefined)[] = samples.map(s => s.lines_pbt)
  const linesCode: (number | null | undefined)[] = samples.map(s => s.lines_code)

  const variants: (string | null | undefined)[] = samples.map(s => s.variant)
  const byVariant = countByValue(variants)

  const models: (string | null | undefined)[] = samples.map(s => s.model)
  const byModel = countByValue(models)

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

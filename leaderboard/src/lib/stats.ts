/**
 * Statistical utility functions for dataset analysis.
 */

/**
 * Calculate mean of an array of numbers, filtering out null/undefined.
 */
export function calculateMean(values: (number | null | undefined)[]): number | null {
  const valid = values.filter((v): v is number => typeof v === 'number' && !isNaN(v))
  if (valid.length === 0) return null
  return valid.reduce((sum, v) => sum + v, 0) / valid.length
}

/**
 * Calculate median of an array of numbers, filtering out null/undefined.
 */
export function calculateMedian(values: (number | null | undefined)[]): number | null {
  const valid = values.filter((v): v is number => typeof v === 'number' && !isNaN(v))
  if (valid.length === 0) return null

  const sorted = [...valid].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)

  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2
  }
  return sorted[mid]
}

/**
 * Calculate a specific quartile (0.25 for Q1, 0.75 for Q3).
 */
export function calculateQuartile(
  values: (number | null | undefined)[],
  quartile: number
): number | null {
  const valid = values.filter((v): v is number => typeof v === 'number' && !isNaN(v))
  if (valid.length === 0) return null

  const sorted = [...valid].sort((a, b) => a - b)
  const pos = (sorted.length - 1) * quartile
  const base = Math.floor(pos)
  const rest = pos - base

  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base])
  }
  return sorted[base]
}

/**
 * Calculate min value of an array, filtering out null/undefined.
 */
export function calculateMin(values: (number | null | undefined)[]): number | null {
  const valid = values.filter((v): v is number => typeof v === 'number' && !isNaN(v))
  if (valid.length === 0) return null
  return Math.min(...valid)
}

/**
 * Calculate max value of an array, filtering out null/undefined.
 */
export function calculateMax(values: (number | null | undefined)[]): number | null {
  const valid = values.filter((v): v is number => typeof v === 'number' && !isNaN(v))
  if (valid.length === 0) return null
  return Math.max(...valid)
}

/**
 * Distribution statistics for a metric.
 */
export interface DistributionStats {
  mean: number | null
  median: number | null
  q1: number | null
  q3: number | null
  min: number | null
  max: number | null
}

/**
 * Calculate full distribution statistics for a set of values.
 */
export function calculateDistribution(values: (number | null | undefined)[]): DistributionStats {
  return {
    mean: calculateMean(values),
    median: calculateMedian(values),
    q1: calculateQuartile(values, 0.25),
    q3: calculateQuartile(values, 0.75),
    min: calculateMin(values),
    max: calculateMax(values),
  }
}

/**
 * Count occurrences of each unique value in an array.
 */
export function countByValue<T extends string | number>(
  values: (T | null | undefined)[]
): Record<string, number> {
  const counts: Record<string, number> = {}

  for (const value of values) {
    if (value !== null && value !== undefined) {
      const key = String(value)
      counts[key] = (counts[key] || 0) + 1
    }
  }

  return counts
}

/**
 * Get top N entries from a count record, sorted by count descending.
 */
export function getTopEntries(
  counts: Record<string, number>,
  limit: number
): Array<{ key: string; count: number }> {
  return Object.entries(counts)
    .map(([key, count]) => ({ key, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit)
}

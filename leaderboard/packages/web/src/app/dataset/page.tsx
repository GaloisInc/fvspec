import type { Metadata } from 'next'
import { DatasetStats } from '@/components/dataset-stats'
import type { DatasetStats as DatasetStatsType } from '@fvspec/common'

export const metadata: Metadata = {
  title: 'Dataset Overview | fvspec Benchmark',
  description:
    'Aggregate statistics and visualizations for the fvspec formal verification benchmark dataset',
}

// This runs on the server during SSR, so we need a full URL (not relative /api)
// Use internal localhost URL to bypass nginx
const API_URL = process.env.API_INTERNAL_URL || 'http://localhost:3002'

async function getStats(): Promise<DatasetStatsType | null> {
  try {
    const res = await fetch(`${API_URL}/dataset/stats`, {
      cache: 'no-store', // Always fetch fresh data for now
    })

    if (!res.ok) {
      throw new Error(`Failed to fetch stats: ${res.statusText}`)
    }

    return res.json()
  } catch (error) {
    console.error('Error fetching stats:', error)
    return null
  }
}

export default async function DatasetIndexPage() {
  const stats = await getStats()

  if (!stats) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
        <main className="container mx-auto px-4 py-8">
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
            <h2 className="text-lg font-semibold text-red-900 dark:text-red-100">
              Failed to load dataset statistics
            </h2>
            <p className="mt-2 text-sm text-red-700 dark:text-red-300">
              The dataset may not be loaded. Please check the API logs.
            </p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
      <main className="container mx-auto px-4 py-8">
        <DatasetStats stats={stats} />
      </main>
    </div>
  )
}

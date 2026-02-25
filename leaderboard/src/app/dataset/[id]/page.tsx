'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { DatasetExplorer } from '@/components/dataset-explorer'
import type { DatasetSampleDetail } from '@fvspec/common'

const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

export default function DatasetPage() {
  const params = useParams()
  const id = params.id as string

  const [sample, setSample] = useState<DatasetSampleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchSample() {
      try {
        const res = await fetch(`${API_URL}/dataset/${id}`, {
          cache: 'no-store',
        })

        if (!res.ok) {
          if (res.status === 404) {
            setError('Sample not found')
          } else {
            throw new Error(`Failed to fetch sample: ${res.statusText}`)
          }
          return
        }

        const data = await res.json()
        setSample(data)
      } catch (err) {
        console.error('Error fetching sample:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchSample()
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
        <main className="container mx-auto px-4 py-8">
          <div className="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-gray-900">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
            <p className="mt-4 text-gray-600 dark:text-gray-400">Loading sample...</p>
          </div>
        </main>
      </div>
    )
  }

  if (error || !sample) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
        <main className="container mx-auto px-4 py-8">
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
            <h2 className="text-lg font-semibold text-red-900 dark:text-red-100">
              {error === 'Sample not found' ? 'Sample Not Found' : 'Failed to Load Sample'}
            </h2>
            <p className="mt-2 text-sm text-red-700 dark:text-red-300">
              {error === 'Sample not found'
                ? `Sample with ID ${id} does not exist.`
                : error || 'Could not load the requested sample. Please try again.'}
            </p>
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              API URL: {API_URL}/dataset/{id}
            </p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
      <main className="container mx-auto px-4 py-8">
        <DatasetExplorer initialSample={sample} />
      </main>
    </div>
  )
}

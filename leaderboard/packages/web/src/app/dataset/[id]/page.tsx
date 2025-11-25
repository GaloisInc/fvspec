import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { DatasetExplorer } from '@/components/dataset-explorer'
import type { DatasetSampleDetail } from '@fvspec/common'

// This runs on the server during SSR, so we need a full URL (not relative /api)
// Use internal localhost URL to bypass nginx
const API_URL = process.env.API_INTERNAL_URL || 'http://localhost:3002'

async function getSample(id: string): Promise<DatasetSampleDetail | null> {
  try {
    const res = await fetch(`${API_URL}/dataset/${id}`, {
      cache: 'no-store', // Always fetch fresh data for now
    })

    if (!res.ok) {
      if (res.status === 404) {
        return null
      }
      throw new Error(`Failed to fetch sample: ${res.statusText}`)
    }

    return res.json()
  } catch (error) {
    console.error('Error fetching sample:', error)
    return null
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>
}): Promise<Metadata> {
  const { id } = await params
  const sample = await getSample(id)

  if (!sample) {
    return {
      title: 'Sample Not Found | fvspec Dataset',
    }
  }

  return {
    title: `${sample.sample_name} | fvspec Dataset`,
    description:
      sample.summary || `View benchmark sample ${sample.sample_id}: ${sample.sample_name}`,
  }
}

export default async function DatasetPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const sample = await getSample(id)

  if (!sample) {
    notFound()
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
      <main className="container mx-auto px-4 py-8">
        <DatasetExplorer initialSample={sample} />
      </main>
    </div>
  )
}

'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import type { DatasetSampleDetail, DatasetSampleListItem } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Shuffle } from 'lucide-react'
import { CodeBlock } from './code-block'

// Client component - use relative URL that goes through Next.js route handler
const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api'

interface DatasetExplorerProps {
    initialSample: DatasetSampleDetail
}

export function DatasetExplorer({ initialSample }: DatasetExplorerProps) {
    const router = useRouter()
    const [samples, setSamples] = useState<DatasetSampleListItem[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        async function loadSamples() {
            try {
                const res = await fetch(`${API_URL}/dataset/list`)
                if (!res.ok) {
                    throw new Error('Failed to load sample list')
                }
                const data = await res.json()
                setSamples(data.samples)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load samples')
            } finally {
                setLoading(false)
            }
        }

        loadSamples()
    }, [])

    const handleSampleChange = (sampleId: string) => {
        router.push(`/dataset/${sampleId}`)
    }

    const handleRandomSample = () => {
        if (samples.length > 0) {
            const randomIndex = Math.floor(Math.random() * samples.length)
            const randomId = samples[randomIndex].sample_id
            router.push(`/dataset/${randomId}`)
        }
    }

    return (
        <div className="space-y-6">
            {/* Pre-alpha warning banner */}
            <Alert>
                <AlertDescription>
                    <strong>Early Development Dataset:</strong> This preview contains{' '}
                    {samples.length} samples while we work out generation pipeline kinks.
                </AlertDescription>
            </Alert>

            {/* Sample selector */}
            <Card>
                <CardHeader>
                    <CardTitle>Sample Selection</CardTitle>
                    <CardDescription>Choose a benchmark sample to explore</CardDescription>
                </CardHeader>
                <CardContent className="flex gap-4">
                    <Select
                        value={initialSample.sample_id.toString()}
                        onValueChange={handleSampleChange}
                        disabled={loading || error !== null}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select a sample..." />
                        </SelectTrigger>
                        <SelectContent>
                            {samples.map(sample => (
                                <SelectItem
                                    key={sample.sample_id}
                                    value={sample.sample_id.toString()}
                                >
                                    {sample.sample_id} - {sample.sample_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Button
                        variant="outline"
                        onClick={handleRandomSample}
                        disabled={loading || samples.length === 0}
                        title="Random sample"
                        className="gap-2"
                    >
                        <Shuffle className="h-4 w-4" />
                        <span className="hidden sm:inline">Random</span>
                    </Button>
                </CardContent>
            </Card>

            {/* Metadata display */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {initialSample.sample_name}
                        <Badge variant="outline">ID: {initialSample.sample_id}</Badge>
                    </CardTitle>
                    {initialSample.realpbt_summary && (
                        <CardDescription>{initialSample.realpbt_summary}</CardDescription>
                    )}
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                        {initialSample.realpbt_repo_id !== undefined && (
                            <Badge variant="outline" className="font-mono text-xs">
                                Repo: {initialSample.realpbt_repo_id}
                            </Badge>
                        )}
                    </div>

                    {/* Metrics */}
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        {initialSample.realpbt_lines_pbt != null && (
                            <div>
                                <div className="text-sm text-muted-foreground">PBT Lines</div>
                                <div className="text-2xl font-bold">
                                    {initialSample.realpbt_lines_pbt}
                                </div>
                            </div>
                        )}
                        {initialSample.lean_metrics?.total_lean_lines != null && (
                            <div>
                                <div className="text-sm text-muted-foreground">Lean Lines</div>
                                <div className="text-2xl font-bold">
                                    {initialSample.lean_metrics.total_lean_lines}
                                </div>
                            </div>
                        )}
                        {initialSample.num_theorems !== undefined && (
                            <div>
                                <div className="text-sm text-muted-foreground">Theorems</div>
                                <div className="text-2xl font-bold">
                                    {initialSample.num_theorems}
                                </div>
                            </div>
                        )}
                        {initialSample.structural_faithfulness?.overall !== undefined && (
                            <div>
                                <div className="text-sm text-muted-foreground">Faithfulness</div>
                                <div className="text-2xl font-bold">
                                    {(
                                        Number(initialSample.structural_faithfulness.overall) * 100
                                    ).toFixed(1)}
                                    %
                                </div>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Code viewer with tabs */}
            <Card>
                <CardHeader>
                    <CardTitle>Code</CardTitle>
                    <CardDescription>View Python source and generated Lean files</CardDescription>
                </CardHeader>
                <CardContent>
                    <Tabs defaultValue="spec" className="w-full">
                        <TabsList className="grid w-full grid-cols-3">
                            <TabsTrigger value="python">Python</TabsTrigger>
                            <TabsTrigger value="spec">Spec</TabsTrigger>
                            <TabsTrigger value="impl">Impl</TabsTrigger>
                        </TabsList>
                        <TabsContent value="python" className="mt-4">
                            <CodeBlock code={initialSample.realpbt_code ?? ''} language="python" />
                        </TabsContent>
                        <TabsContent value="spec" className="mt-4">
                            <CodeBlock code={initialSample.spec} language="lean4" />
                        </TabsContent>
                        <TabsContent value="impl" className="mt-4">
                            <CodeBlock code={initialSample.impl} language="lean4" />
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
        </div>
    )
}

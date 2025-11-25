'use client'

import Link from 'next/link'
import type { DatasetStats as DatasetStatsType } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface DatasetStatsProps {
  stats: DatasetStatsType
}

function formatNumber(value: number | null): string {
  if (value === null) return 'N/A'
  return value.toFixed(2)
}

function formatInteger(value: number | null): string {
  if (value === null) return 'N/A'
  return Math.round(value).toString()
}

export function DatasetStats({ stats }: DatasetStatsProps) {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Dataset Overview</h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Aggregate statistics and insights across all benchmark samples
        </p>
      </div>

      {/* Pre-alpha warning banner */}
      <Alert>
        <AlertDescription>
          <strong>Early Development Dataset:</strong> This preview contains {stats.total} samples
          while we work out generation pipeline kinks. The final benchmark will be{' '}
          <strong>2+ orders of magnitude larger</strong> with significantly improved specification
          quality. Current samples are experimental and may contain imperfect translations.
        </AlertDescription>
      </Alert>

      {/* Summary statistics grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Samples</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Mean Faithfulness</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{formatNumber(stats.faithfulness.mean)}</div>
            <p className="mt-1 text-xs text-muted-foreground">Structural similarity score</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Mean Theorems</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{formatNumber(stats.theorems.mean)}</div>
            <p className="mt-1 text-xs text-muted-foreground">Avg theorems per sample</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Mean Lean Lines</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{formatNumber(stats.lines_code.mean)}</div>
            <p className="mt-1 text-xs text-muted-foreground">Lines of Lean code</p>
          </CardContent>
        </Card>
      </div>

      {/* Distribution statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Distribution Statistics</CardTitle>
          <CardDescription>Quartiles (Q1, Median, Q3) and ranges for key metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Metric</TableHead>
                <TableHead className="text-right">Min</TableHead>
                <TableHead className="text-right">Q1</TableHead>
                <TableHead className="text-right">Median</TableHead>
                <TableHead className="text-right">Q3</TableHead>
                <TableHead className="text-right">Max</TableHead>
                <TableHead className="text-right">Mean</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">Faithfulness Score</TableCell>
                <TableCell className="text-right">{formatNumber(stats.faithfulness.min)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.faithfulness.q1)}</TableCell>
                <TableCell className="text-right">
                  {formatNumber(stats.faithfulness.median)}
                </TableCell>
                <TableCell className="text-right">{formatNumber(stats.faithfulness.q3)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.faithfulness.max)}</TableCell>
                <TableCell className="text-right">
                  {formatNumber(stats.faithfulness.mean)}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Theorem Count</TableCell>
                <TableCell className="text-right">{formatInteger(stats.theorems.min)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.theorems.q1)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.theorems.median)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.theorems.q3)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.theorems.max)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.theorems.mean)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">PBT Lines</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_pbt.min)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_pbt.q1)}</TableCell>
                <TableCell className="text-right">
                  {formatInteger(stats.lines_pbt.median)}
                </TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_pbt.q3)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_pbt.max)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.lines_pbt.mean)}</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Lean Code Lines</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_code.min)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_code.q1)}</TableCell>
                <TableCell className="text-right">
                  {formatInteger(stats.lines_code.median)}
                </TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_code.q3)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lines_code.max)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.lines_code.mean)}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Breakdown by variant */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Breakdown by Variant</CardTitle>
            <CardDescription>Distribution across functional vs MVCGen approaches</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.by_variant)
                .sort((a, b) => b[1] - a[1])
                .map(([variant, count]) => (
                  <div key={variant} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{variant || 'Unknown'}</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-sm text-muted-foreground">
                        {((count / stats.total) * 100).toFixed(1)}%
                      </div>
                      <div className="text-lg font-semibold">{count}</div>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Breakdown by Model</CardTitle>
            <CardDescription>Distribution across different generation models</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(stats.by_model)
                .sort((a, b) => b[1] - a[1])
                .map(([model, count]) => (
                  <div key={model} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{model || 'Unknown'}</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-sm text-muted-foreground">
                        {((count / stats.total) * 100).toFixed(1)}%
                      </div>
                      <div className="text-lg font-semibold">{count}</div>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top repositories */}
      <Card>
        <CardHeader>
          <CardTitle>Top Source Repositories</CardTitle>
          <CardDescription>Most frequent source repositories in the dataset</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rank</TableHead>
                <TableHead>Repository ID</TableHead>
                <TableHead className="text-right">Sample Count</TableHead>
                <TableHead className="text-right">Percentage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.by_repo.map((repo, index) => (
                <TableRow key={repo.key}>
                  <TableCell className="font-medium">{index + 1}</TableCell>
                  <TableCell>
                    <code className="rounded bg-muted px-1.5 py-0.5 text-sm">{repo.key}</code>
                  </TableCell>
                  <TableCell className="text-right">{repo.count}</TableCell>
                  <TableCell className="text-right">
                    {((repo.count / stats.total) * 100).toFixed(1)}%
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Call to action */}
      <Card>
        <CardHeader>
          <CardTitle>Explore Individual Samples</CardTitle>
          <CardDescription>
            Browse the dataset to see Python property-based tests and their generated Lean
            specifications
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/dataset/341">
            <Button size="lg">Browse Samples →</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}

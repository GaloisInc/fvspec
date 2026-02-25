'use client'

import Link from 'next/link'
import type { DatasetStats as DatasetStatsType } from '@fvspec/common'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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

      {/* Summary statistics grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
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
            <CardDescription>Mean Difficulty</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{formatNumber(stats.difficulty.mean)}</div>
            <p className="mt-1 text-xs text-muted-foreground">Haiku subjective (1-10)</p>
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
            <div className="text-3xl font-bold">{formatNumber(stats.lean_lines.mean)}</div>
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
                <TableCell className="font-medium">Difficulty (Haiku)</TableCell>
                <TableCell className="text-right">{formatNumber(stats.difficulty.min)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.difficulty.q1)}</TableCell>
                <TableCell className="text-right">
                  {formatNumber(stats.difficulty.median)}
                </TableCell>
                <TableCell className="text-right">{formatNumber(stats.difficulty.q3)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.difficulty.max)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.difficulty.mean)}</TableCell>
              </TableRow>
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
                <TableCell className="font-medium">Lean Lines</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lean_lines.min)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lean_lines.q1)}</TableCell>
                <TableCell className="text-right">
                  {formatInteger(stats.lean_lines.median)}
                </TableCell>
                <TableCell className="text-right">{formatInteger(stats.lean_lines.q3)}</TableCell>
                <TableCell className="text-right">{formatInteger(stats.lean_lines.max)}</TableCell>
                <TableCell className="text-right">{formatNumber(stats.lean_lines.mean)}</TableCell>
              </TableRow>
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
          <Link href="/dataset/1">
            <Button size="lg">Browse Samples →</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Pre-compute dataset stats, list, and individual sample files from JSONL.
 *
 * Reads the full dataset once at build time and writes:
 *   data/stats.json         — aggregate distribution statistics
 *   data/list.json          — minimal sample list (id, name, difficulty)
 *   data/samples/<id>.json  — individual sample detail files
 *
 * This avoids fetching 178MB from S3 on every Vercel cold start.
 *
 * Sources (checked in order):
 *   1. CLI argument:     tsx scripts/precompute-dataset.ts path/to/fvspec.jsonl
 *   2. Env DATASET_PATH: local file path
 *   3. Env DATASET_URL:  remote URL
 *   4. Default S3 URL
 */

import fs from 'node:fs'
import path from 'node:path'
import { DatasetSampleDetailSchema, type DifficultyBinary } from '../src/lib/schemas/dataset'
import { calculateDistribution } from '../src/lib/stats'

const DEFAULT_DATASET_URL = 'https://fvspec-vercel-assets.s3.us-west-2.amazonaws.com/fvspec.jsonl'

async function getDatasetContent(): Promise<string> {
  // 1. CLI argument
  const cliPath = process.argv[2]
  if (cliPath) {
    const resolved = path.resolve(process.cwd(), cliPath)
    if (!fs.existsSync(resolved)) {
      console.error(`Dataset file not found: ${resolved}`)
      process.exit(1)
    }
    console.log(`Reading dataset from ${resolved}...`)
    return fs.readFileSync(resolved, 'utf-8')
  }

  // 2. DATASET_PATH env
  if (process.env.DATASET_PATH) {
    const resolved = path.resolve(process.cwd(), process.env.DATASET_PATH)
    if (!fs.existsSync(resolved)) {
      console.error(`DATASET_PATH file not found: ${resolved}`)
      process.exit(1)
    }
    console.log(`Reading dataset from ${resolved}...`)
    return fs.readFileSync(resolved, 'utf-8')
  }

  // 3. DATASET_URL or default S3
  const url = process.env.DATASET_URL || DEFAULT_DATASET_URL
  console.log(`Fetching dataset from ${url}...`)
  const response = await fetch(url)
  if (!response.ok) {
    console.error(`Failed to fetch dataset: ${response.status} ${response.statusText}`)
    process.exit(1)
  }
  return response.text()
}

const content = await getDatasetContent()
const lines = content.split('\n').filter(line => line.trim().length > 0)

console.log(`Parsing ${lines.length} samples...`)

const list: Array<{
  sample_id: number
  sample_name: string
  difficulty_binary: DifficultyBinary | null
}> = []
const faithfulnessScores: (number | undefined)[] = []
const theorems: (number | undefined)[] = []
const leanLines: (number | undefined)[] = []
const difficultyCounts = { easy: 0, hard: 0, unknown: 0 }

let parsed = 0
let skipped = 0

// First pass: collect stats and list data, store validated samples for file writing
const validatedSamples: Array<{ sample_id: number; data: unknown }> = []

for (let i = 0; i < lines.length; i++) {
  try {
    const raw = JSON.parse(lines[i])
    const result = DatasetSampleDetailSchema.safeParse(raw)

    if (!result.success) {
      skipped++
      if (skipped <= 5) {
        console.warn(
          `Line ${i + 1}: Invalid sample:`,
          result.error.issues?.[0]?.message ?? result.error
        )
      }
      continue
    }

    const sample = result.data
    parsed++

    list.push({
      sample_id: sample.sample_id,
      sample_name: sample.sample_name,
      difficulty_binary: sample.difficulty_binary ?? null,
    })

    faithfulnessScores.push(sample.structural_faithfulness?.overall as number | undefined)
    theorems.push(sample.num_theorems)
    leanLines.push(sample.lean_metrics?.total_lean_lines)
    if (sample.difficulty_binary === 'easy') difficultyCounts.easy++
    else if (sample.difficulty_binary === 'hard') difficultyCounts.hard++
    else difficultyCounts.unknown++

    validatedSamples.push({ sample_id: sample.sample_id, data: result.data })
  } catch {
    skipped++
    if (skipped <= 5) {
      console.warn(`Line ${i + 1}: Failed to parse JSON`)
    }
  }
}

list.sort((a, b) => a.sample_id - b.sample_id)

const stats = {
  total: parsed,
  faithfulness: calculateDistribution(faithfulnessScores),
  theorems: calculateDistribution(theorems),
  lean_lines: calculateDistribution(leanLines),
  difficulty: difficultyCounts,
}

const outDir = path.resolve(import.meta.dirname, '..', 'data')
const samplesDir = path.join(outDir, 'samples')
fs.mkdirSync(outDir, { recursive: true })
fs.mkdirSync(samplesDir, { recursive: true })

const statsPath = path.join(outDir, 'stats.json')
const listPath = path.join(outDir, 'list.json')

fs.writeFileSync(statsPath, JSON.stringify(stats, null, 2))
fs.writeFileSync(listPath, JSON.stringify(list))

// Write individual sample files for the detail view
console.log(`Writing ${validatedSamples.length} individual sample files...`)
for (const { sample_id, data } of validatedSamples) {
  const samplePath = path.join(samplesDir, `${sample_id}.json`)
  fs.writeFileSync(samplePath, JSON.stringify(data))
}

console.log(`Wrote ${statsPath} (${fs.statSync(statsPath).size} bytes)`)
console.log(`Wrote ${listPath} (${fs.statSync(listPath).size} bytes)`)
console.log(`Wrote ${validatedSamples.length} sample files to ${samplesDir}`)
console.log(`Done: ${parsed} samples parsed, ${skipped} skipped`)

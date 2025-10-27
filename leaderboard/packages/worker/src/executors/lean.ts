import { mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { run } from '../lib/exec.js'
import { sha256File } from '../lib/hash.js'

export async function executeLeanBuild(opts: {
  repoUrl: string
  commitSha: string
  timeLimitSec: number
  memoryMB: number
  artifactsDir: string
  toolchainImage?: string // docker image with lean/lake
}) {
  const work = await mkwork()
  const logs: string[] = []
  const cmdLogs = async (title: string, fn: () => Promise<{ exitCode: number; log: string }>) => {
    const res = await fn()
    logs.push(`\n## ${title}\n${res.log}`)
    if (res.exitCode !== 0) throw new Error(`${title} failed with code ${res.exitCode}`)
  }

  if (opts.toolchainImage) {
    // Dockerized path
    await cmdLogs('git clone', () => run('git', ['clone', opts.repoUrl, 'repo'], { cwd: work }))
    await cmdLogs('git checkout', () =>
      run('git', ['checkout', opts.commitSha], {
        cwd: join(work, 'repo'),
      })
    )
    const repoDir = join(work, 'repo')

    // bind mount repo & artifacts; run inside container
    const containerLogs = await run(
      'docker',
      [
        'run',
        '--rm',
        '--name',
        `leanbuild-${process.pid}-${Date.now()}`,
        '--network',
        'none',
        '--memory',
        `${opts.memoryMB}m`,
        '--cpus',
        '2',
        '-v',
        `${repoDir}:/workspace:rw`,
        '-v',
        `${opts.artifactsDir}:/artifacts:rw`,
        '-w',
        '/workspace',
        opts.toolchainImage,
        'bash',
        '-lc',
        [
          'set -euo pipefail',
          'lake update',
          `timeout ${opts.timeLimitSec}s lake build`,
          'mkdir -p /artifacts/results',
          'if [ -f results/summary.json ]; then cp -r results/* /artifacts/results/; fi || true',
        ].join(' && '),
      ],
      { timeoutSec: opts.timeLimitSec + 120 }
    )
    logs.push(`\n## docker build\n${containerLogs.log}`)
  } else {
    // Host tooling path (assumes lean/lake installed)
    await cmdLogs('git clone', () =>
      run('git', ['clone', '--depth', '1', '--no-single-branch', opts.repoUrl, 'repo'], {
        cwd: work,
      })
    )
    await cmdLogs('git checkout', () =>
      run('git', ['checkout', opts.commitSha], {
        cwd: join(work, 'repo'),
      })
    )
    await cmdLogs('lake update', () => run('lake', ['update'], { cwd: join(work, 'repo') }))
    await cmdLogs('lake build', () =>
      run('bash', ['-lc', `timeout ${opts.timeLimitSec}s lake build`], {
        cwd: join(work, 'repo'),
        timeoutSec: opts.timeLimitSec + 30,
      })
    )
  }

  // Collect artifact hashes if present
  const resultsPath = join(opts.artifactsDir, 'results/summary.json')
  const artifacts = []
  try {
    artifacts.push({
      path: 'results/summary.json',
      sha256: await sha256File(resultsPath),
    })
  } catch {
    // Artifact file may not exist if build failed
  }

  const combinedLog = logs.join('\n')
  const logPath = join(opts.artifactsDir, `build-${Date.now()}.log`)
  await mkdir(opts.artifactsDir, { recursive: true })
  await writeFile(logPath, combinedLog)

  return { artifacts, logPath }
}

async function mkwork() {
  const dir = join(tmpdir(), `lean-work-${process.pid}-${Date.now()}`)
  await mkdir(dir, { recursive: true })
  return dir
}

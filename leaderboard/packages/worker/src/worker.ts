import { Worker, QueueEvents, type Job } from 'bullmq'
import IORedis from 'ioredis'
import { SubmissionJob, type SubmissionJob as SubmissionJobType } from './lib/job-schema.js'
import { executeLeanBuild } from './executors/lean.js'
import { buildAttestation } from './lib/attestation.js'
import { reportResults } from './lib/report.js'

const connection = new IORedis(process.env.REDIS_URL!)
const queueName = 'submissions'

const worker = new Worker<SubmissionJobType>(
  queueName,
  async (job: Job<SubmissionJobType>) => {
    const data: SubmissionJobType = SubmissionJob.parse(job.data)
    const startedAt = new Date().toISOString()

    const { artifacts, logPath } = await executeLeanBuild({
      repoUrl: data.repoUrl,
      commitSha: data.commitSha,
      timeLimitSec: Number(process.env.TIME_LIMIT_SEC ?? 7200),
      memoryMB: Number(process.env.MEMORY_MB ?? 16000),
      artifactsDir: process.env.ARTIFACTS_DIR ?? '/tmp/leaderboard_artifacts',
      toolchainImage: process.env.TOOLCHAIN_IMAGE,
    })

    const finishedAt = new Date().toISOString()
    const attestation = buildAttestation({
      submissionId: data.submissionId,
      repoUrl: data.repoUrl,
      commitSha: data.commitSha,
      trackId: data.trackId,
      toolchain: { imageDigest: process.env.TOOLCHAIN_IMAGE },
      runner: {
        name: process.env.RUNNER_NAME ?? 'runner',
        trust: (process.env.RUNNER_TRUST ?? 'internal') as 'internal' | 'partner' | 'community',
      },
      startedAt,
      finishedAt,
      artifacts,
      limits: {
        timeSec: Number(process.env.TIME_LIMIT_SEC ?? 7200),
        memoryMB: Number(process.env.MEMORY_MB ?? 16000),
      },
    })

    // TODO: parse results/summary.json for metrics if your harness writes it
    const resultsBody = {
      submissionId: data.submissionId,
      runId: data.runId,
      status: 'succeeded',
      metrics: { score: null, passRate: null, avgTime: null }, // fill from results
      attestation,
      logs: { logPath }, // or upload to S3 and send URL instead
    }

    await reportResults(process.env.API_BASE_URL!, process.env.API_TOKEN!, resultsBody)
  },
  {
    connection,
    concurrency: Number(process.env.WORKER_CONCURRENCY ?? 1),
  }
)

const qe = new QueueEvents(queueName, { connection })
qe.on('failed', ({ jobId, failedReason }) => {
  console.error('[failed]', jobId, failedReason)
})
qe.on('completed', ({ jobId }) => {
  console.log('[completed]', jobId)
})

process.on('SIGINT', () => {
  void (async () => {
    await worker.close()
    await qe.close()
    process.exit(0)
  })()
})
process.on('SIGTERM', () => {
  void (async () => {
    await worker.close()
    await qe.close()
    process.exit(0)
  })()
})

console.log(`worker up for queue="${queueName}" on ${process.env.REDIS_URL}`)

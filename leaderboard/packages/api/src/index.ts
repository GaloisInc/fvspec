import { Hono } from 'hono'
import { Queue } from 'bullmq'
import IORedis from 'ioredis'
import { CreateSubmissionSchema } from '@fvspec/common'

const app = new Hono()
const queue = new Queue('submissions', {
  connection: new IORedis(process.env.REDIS_URL!),
})

app.get('/', c => c.json({ ok: true }))

app.post('/submit', async c => {
  const body: unknown = await c.req.json()
  const data = CreateSubmissionSchema.parse(body)
  const submissionId = 123 // TODO insert & return id
  await queue.add(
    'run',
    { submissionId, ...data },
    {
      attempts: 5,
      backoff: { type: 'exponential', delay: 5000 },
    }
  )
  return c.json({ ok: true, submissionId })
})

app.fire() // starts on PORT or 3000

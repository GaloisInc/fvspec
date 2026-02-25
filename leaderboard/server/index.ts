import 'dotenv/config'
import { serve } from '@hono/node-server'
import app from '../src/lib/api.js'

const port = Number(process.env.PORT) || 3001

serve(
  {
    fetch: app.fetch,
    port,
  },
  info => {
    console.log(`API listening on http://localhost:${info.port}`)
  }
)

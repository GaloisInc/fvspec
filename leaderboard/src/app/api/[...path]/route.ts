import app from '@/lib/api'
import { handle } from 'hono/vercel'

export const runtime = 'nodejs'

const handler = handle(app)

export const GET = handler
export const POST = handler
export const PUT = handler
export const DELETE = handler
export const OPTIONS = handler

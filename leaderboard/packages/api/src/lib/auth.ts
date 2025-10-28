import type { Context, Next } from 'hono'

/**
 * Middleware to validate API token for internal endpoints
 * Used by worker to authenticate when POSTing results
 */
export async function requireApiToken(c: Context, next: Next) {
  const authHeader = c.req.header('authorization')
  const expectedToken = process.env.API_TOKEN

  if (!expectedToken) {
    console.warn('API_TOKEN not set in environment - authentication disabled')
    return next()
  }

  if (!authHeader) {
    return c.json({ error: 'Missing authorization header' }, 401)
  }

  const token = authHeader.replace(/^Bearer\s+/i, '')

  if (token !== expectedToken) {
    return c.json({ error: 'Invalid API token' }, 403)
  }

  return next()
}

import { fetch } from 'undici'

export async function reportResults(apiBase: string, token: string, body: unknown): Promise<void> {
  const res = await fetch(`${apiBase}/results`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`results report failed: ${res.status} ${await res.text()}`)
}

// Legacy alias for backwards compatibility
export const reportIngest = reportResults

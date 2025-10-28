import { fetch } from 'undici'

export async function reportIngest(apiBase: string, token: string, body: unknown): Promise<void> {
  const res = await fetch(`${apiBase}/ingest`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`ingest failed: ${res.status} ${await res.text()}`)
}

// Typed access to the local backend. Will be generated from the OpenAPI
// schema once the API grows (docs/ARCHITECTURE.md §5).
export interface Health {
  app: string
  version: string
  schema: number
}

export async function getHealth(): Promise<Health> {
  const r = await fetch('/api/health')
  if (!r.ok) throw new Error(`backend answered ${r.status}`)
  return (await r.json()) as Health
}

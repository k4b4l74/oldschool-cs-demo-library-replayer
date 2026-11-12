// Typed access to the local backend. Types come from the backend's OpenAPI
// schema (python3 tasks.py api-types); never edit schema.d.ts by hand.
import type { components } from './schema'

type S = components['schemas']
export type Health = S['Health']
export type LibraryStats = S['LibraryStats']
export type MatchSummary = S['MatchSummary']
export type MatchPage = S['MatchPage']
export type MatchDetail = S['MatchDetail']
export type MatchDemo = S['MatchDemo']
export type Lineup = S['Lineup']
export type DemoRounds = S['DemoRounds']
export type Round = S['Round']
export type Kill = S['Kill']
export type PlayerSummary = S['PlayerSummary']
export type PlayerDetail = S['PlayerDetail']
export type TeamSummary = S['TeamSummary']
export type TeamDetail = S['TeamDetail']
export type Engine = S['Engine']
export type EngineRoute = S['EngineRoute']
export type EnginesView = S['EnginesView']
export type EnginePatch = S['EnginePatch']
export type Settings = S['Settings']
export type SettingsChange = S['SettingsChange']
export type Bind = S['Bind']
export type ControlAction = S['ControlAction']
export type ControlGroup = S['ControlGroup']
export type PlayResponse = S['PlayResponse']
export type ImportsView = S['ImportsView']
export type Job = S['Job']
export type JobDetail = S['JobDetail']
export type JobFile = S['JobFile']
export type Uploaded = S['Uploaded']

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function get<T>(path: string, params?: Record<string, string | string[] | number | undefined>): Promise<T> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v === undefined || v === '') continue
    for (const one of Array.isArray(v) ? v : [String(v)]) qs.append(k, one)
  }
  const url = qs.size ? `${path}?${qs}` : path
  const r = await fetch(url)
  if (!r.ok) throw new ApiError(r.status, `backend answered ${r.status} for ${path}`)
  return (await r.json()) as T
}

/** Changes and Play: the custom header proves the request comes from the app's own pages. */
async function send<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Oldschool': '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    let message = `backend answered ${r.status}`
    try {
      const j = (await r.json()) as { detail?: unknown }
      if (typeof j.detail === 'string') message = j.detail
      else if (Array.isArray(j.detail)) message = j.detail.map((d: { msg?: string }) => d.msg ?? '').join('; ')
    } catch {
      /* not JSON */
    }
    throw new ApiError(r.status, message)
  }
  return (await r.json()) as T
}

export interface MatchQuery {
  q?: string
  player?: string
  steamid?: string
  team?: string
  map?: string
  release?: string[]
  year_from?: string
  year_to?: string
  pov?: '' | 'hltv' | 'player'
  sort?: string
  dir?: 'asc' | 'desc'
  page?: number
  size?: number
}

export const api = {
  health: () => get<Health>('/api/health'),
  stats: () => get<LibraryStats>('/api/stats'),
  matches: (q: MatchQuery) => get<MatchPage>('/api/matches', { ...q }),
  match: (id: number) => get<MatchDetail>(`/api/matches/${id}`),
  rounds: (sha1: string) => get<DemoRounds>(`/api/demos/${sha1}/rounds`),
  players: (q: string) => get<PlayerSummary[]>('/api/players', { q }),
  player: (id: number) => get<PlayerDetail>(`/api/players/${id}`),
  teams: (q: string) => get<TeamSummary[]>('/api/teams', { q }),
  team: (id: number) => get<TeamDetail>(`/api/teams/${id}`),
  engines: () => get<EnginesView>('/api/engines'),
  scanEngines: () => send<{ found: number; roots: number }>('POST', '/api/engines/scan'),
  addEngine: (path: string) => send<Engine>('POST', '/api/engines', { path }),
  patchEngine: (id: number, patch: EnginePatch) => send<Engine>('PATCH', `/api/engines/${id}`, patch),
  deleteEngine: (id: number) => send<{ deleted: number }>('DELETE', `/api/engines/${id}`),
  setRoute: (protocol: number, release: string, engine_id: number | null) => send<EnginesView>('PUT', '/api/routes', { protocol, release, engine_id }),
  settings: () => get<Settings>('/api/settings'),
  saveSettings: (change: SettingsChange) => send<Settings>('PUT', '/api/settings', change),
  imports: () => get<ImportsView>('/api/imports'),
  importDetail: (id: number, status?: string, page = 1) => get<JobDetail>(`/api/imports/${id}`, { status, page, size: 50 }),
  importFolder: (path: string, copy_demos: boolean) => send<Job>('POST', '/api/imports', { path, copy_demos }),
  cancelImport: (id: number) => send<Job>('POST', `/api/imports/${id}/cancel`),
  retryFile: (fileId: number) => send<Job>('POST', `/api/imports/files/${fileId}/retry`),
  reanalyse: (only_outdated: boolean) => send<Job>('POST', '/api/imports/reanalyse', { only_outdated }),
  openDrop: () => send<{ opened: string }>('POST', '/api/drop/open'),
  play: (sha1: string, seek?: number) => send<PlayResponse>('POST', '/api/play', { sha1, seek: seek !== undefined && seek >= 1 ? seek : null }),
}

/** Send one file to the Drop folder, with upload progress (fetch has none). */
export function uploadFile(file: File, onProgress: (sent: number) => void): Promise<Uploaded> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/drop?name=${encodeURIComponent(file.name)}`)
    xhr.setRequestHeader('X-Oldschool', '1')
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = (e) => onProgress(e.loaded)
    xhr.onload = () => {
      let body: { detail?: unknown } & Partial<Uploaded> = {}
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as Uploaded)
      else reject(new ApiError(xhr.status, typeof body.detail === 'string' ? body.detail : `backend answered ${xhr.status}`))
    }
    xhr.onerror = () => reject(new ApiError(0, 'backend not reachable'))
    xhr.send(file)
  })
}

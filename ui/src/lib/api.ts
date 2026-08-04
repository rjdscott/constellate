/** The one fetch layer. Two modes, branched here so callers never know:
 *
 *  - live (default): talks to the FastAPI app at VITE_API_BASE ('' = same origin)
 *  - snapshot: GETs are served from committed static JSON under /snapshot/
 *    (path-derived: /v1/bench-results -> /snapshot/bench-results.json), and
 *    retrieval POSTs throw SnapshotModeError for the UI to render.
 */
import { useQuery } from '@tanstack/react-query'

import type {
  BenchResultEntry,
  Health,
  Item,
  PlatformStatus,
  RetrievalRequest,
  RetrievalResponse,
} from './types.ts'

const BASE: string = import.meta.env.VITE_API_BASE ?? ''
const MODE: string = import.meta.env.VITE_UI_MODE ?? 'live'

export const isSnapshot = MODE === 'snapshot'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Thrown for anything a static snapshot cannot answer. Render, don't retry. */
export class SnapshotModeError extends Error {
  constructor(what: string) {
    super(`${what} requires a live API — this is a static snapshot build.`)
    this.name = 'SnapshotModeError'
  }
}

type Params = Record<string, string | number | boolean | undefined>

function url(path: string, params: Params): string {
  // snapshot: query params can't be honoured by a file, so they're dropped and
  // the path becomes the filename.
  if (isSnapshot) return `${BASE}/snapshot/${path.replace(/^\/v1\//, '')}.json`
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  return `${BASE}${path}${query.size ? `?${query}` : ''}`
}

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const response = await fetch(url(path, params), { headers: { accept: 'application/json' } })
  if (!response.ok) throw new ApiError(response.status, `GET ${path} → ${response.status}`)
  return (await response.json()) as T
}

export async function recommend(
  request: RetrievalRequest,
  platform?: string,
): Promise<RetrievalResponse> {
  if (isSnapshot) throw new SnapshotModeError('Retrieval')
  const response = await fetch(url('/v1/recommend', { platform }), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) throw new ApiError(response.status, `POST /v1/recommend → ${response.status}`)
  return (await response.json()) as RetrievalResponse
}

export const usePlatforms = () =>
  useQuery({ queryKey: ['platforms'], queryFn: () => get<PlatformStatus[]>('/v1/platforms') })

export const useBenchResults = () =>
  useQuery({ queryKey: ['bench-results'], queryFn: () => get<BenchResultEntry[]>('/v1/bench-results') })

export const useBenchResult = (name: string | undefined) =>
  useQuery({
    queryKey: ['bench-results', name],
    queryFn: () => get<Record<string, unknown>>(`/v1/bench-results/${name!}`),
    enabled: Boolean(name),
  })

export const useSearchItems = (q: string, platform?: string) =>
  useQuery({
    queryKey: ['search-items', q, platform],
    queryFn: () => get<Item[]>('/v1/search/items', { q, platform }),
    enabled: q.trim().length > 0,
  })

export const useHealth = (platform?: string) =>
  useQuery({ queryKey: ['health', platform], queryFn: () => get<Health>('/v1/health', { platform }) })

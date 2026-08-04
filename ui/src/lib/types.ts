/** TS mirrors of `src/constellate/core/types.py` + the API's response shapes.
 *  Field names are the wire format (snake_case) — deliberately not remapped to
 *  camelCase, so a response can be read straight against the pydantic model. */

export type ItemId = number
export type UserId = number
export type PlaneName = 'relational' | 'vector' | 'graph'

export interface Item {
  item_id: ItemId
  title: string
  year: number | null
  genres: string[]
  popularity: number
  n_ratings: number
  mean_rating: number | null
}

export interface UserContext {
  user_id: UserId
  n_ratings: number
  region: string | null
  tier: string | null
}

export interface Candidate {
  item_id: ItemId
  score: number
  source: PlaneName
  /** graph traversal, e.g. ["u:5", "rated", "m:318"] */
  path: string[] | null
  hops: number | null
}

export interface Recommendation {
  item_id: ItemId
  rank: number
  score: number
  sources: PlaneName[]
  /** rendered prose, only when explain=true */
  reason: string | null
  /** same path unrendered — the graph view draws this */
  path: string[] | null
  metadata: Record<string, unknown>
}

export interface RetrievalRequest {
  user_id?: UserId | null
  seed_item_id?: ItemId | null
  k?: number
  max_hops?: number
  policy?: Record<string, unknown>
  explain?: boolean
  /** null = all planes; a subset is an ablation */
  planes?: PlaneName[] | null
}

export interface StepTimings {
  relational_ms: number
  vector_ms: number
  graph_ms: number
  fusion_ms: number
  total_ms: number
}

export interface RetrievalResponse {
  recommendations: Recommendation[]
  timings: StepTimings
  config_fingerprint: string
}

/** `GET /v1/platforms` — liveness probe per configured platform. */
export interface PlatformStatus {
  platform: string
  alive: boolean
  config_fingerprint: string | null
}

/** `GET /v1/bench-results` — one entry per committed artifact. */
export interface BenchResultEntry {
  name: string
  platform: string | null
  config_fingerprint: string | null
  utc: string | null
}

/** `GET /v1/health` */
export type Health = Record<string, string>

/** `GET /v1/tags` — genome tag id → name, e.g. {"742": "zombies"}. */
export type TagNames = Record<string, string>

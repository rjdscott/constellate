import { useState } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'

import { ApiError } from '../../lib/api.ts'
import { tidyTitle } from '../../lib/format.ts'
import { PLATFORM_META, type PlatformId } from '../../lib/platforms.ts'
import type { PlaneName, Recommendation, RetrievalResponse } from '../../lib/types.ts'
import Constellation from './Constellation.tsx'

function TimingStrip({ timings }: { timings: RetrievalResponse['timings'] }) {
  const parts: { plane: PlaneName | 'fusion'; ms: number; color: string }[] = [
    { plane: 'relational', ms: timings.relational_ms, color: 'var(--data-relational)' },
    { plane: 'vector', ms: timings.vector_ms, color: 'var(--data-vector)' },
    { plane: 'graph', ms: timings.graph_ms, color: 'var(--data-graph)' },
    { plane: 'fusion', ms: timings.fusion_ms, color: 'var(--color-text-dim)' },
  ]
  const sum = parts.reduce((acc, p) => acc + Math.max(p.ms, 0), 0) || 1

  return (
    <div className="mt-3">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-raised">
        {parts.map((p) => (
          <div
            key={p.plane}
            title={`${p.plane} · ${p.ms.toFixed(1)} ms`}
            style={{ width: `${(Math.max(p.ms, 0) / sum) * 100}%`, background: p.color }}
          />
        ))}
      </div>
      <p className="mt-1 text-xs text-text-faint">illustrative · harness is the citable source</p>
    </div>
  )
}

function Skeleton() {
  return (
    <ol className="mt-3 flex flex-col gap-2">
      {[0, 1, 2, 3, 4].map((row) => (
        <li key={row} className="h-[18px] w-full animate-pulse rounded-sm bg-raised" />
      ))}
    </ol>
  )
}

function ErrorState({ error, platform }: { error: unknown; platform: PlatformId }) {
  const message = error instanceof ApiError ? error.message : 'unreachable'
  return (
    <div className="mt-6 flex flex-col items-start gap-2 text-sm">
      <span className="flex items-center gap-2 text-text-dim">
        <span className="size-1.5 rounded-full bg-error" aria-hidden />
        {message}
      </span>
      <span className="font-mono text-xs text-text-faint">make up PLATFORM={platform}</span>
    </div>
  )
}

function List({
  recommendations,
  hoveredId,
  onHover,
  consensusIds,
  explainOn,
  onSelectPath,
}: {
  recommendations: Recommendation[]
  hoveredId: number | null
  onHover: (id: number | null) => void
  consensusIds: Set<number>
  explainOn: boolean
  onSelectPath: (rec: Recommendation) => void
}) {
  return (
    <ol className="mt-3 flex flex-col gap-1.5">
      {recommendations.map((rec) => {
        const { title, year } = tidyTitle(String(rec.metadata.title ?? rec.item_id))
        const clickable = explainOn && rec.path !== null
        return (
          <li
            key={rec.item_id}
            onMouseEnter={() => onHover(rec.item_id)}
            onMouseLeave={() => onHover(null)}
            onClick={() => clickable && onSelectPath(rec)}
            className={`flex items-center gap-2.5 rounded-sm px-1.5 py-1 text-[13px] transition-colors duration-[var(--motion-fast)] ${
              hoveredId === rec.item_id ? 'bg-raised' : ''
            } ${clickable ? 'cursor-pointer' : ''}`}
          >
            <span className="tnum w-5 shrink-0 font-mono text-xs text-text-faint">{rec.rank}</span>
            <span className="min-w-0 flex-1 truncate text-text">
              {title}
              {year && <span className="ml-1.5 text-text-faint">{year}</span>}
              {consensusIds.has(rec.item_id) && (
                <span className="ml-1.5 text-accent" aria-label="consensus across every pane">
                  ✦
                </span>
              )}
            </span>
            <span className="tnum shrink-0 font-mono text-xs text-text-dim">{rec.score.toFixed(4)}</span>
            <span className="flex shrink-0 gap-1">
              {rec.sources.map((source) => (
                <span
                  key={source}
                  title={source}
                  className="size-1.5 rounded-full"
                  style={{ background: `var(--data-${source})` }}
                />
              ))}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default function ResultsPane({
  platform,
  query,
  seedKey,
  explainOn,
  hoveredId,
  onHover,
  consensusIds,
}: {
  platform: PlatformId
  query: UseQueryResult<RetrievalResponse, unknown>
  seedKey: string
  explainOn: boolean
  hoveredId: number | null
  onHover: (id: number | null) => void
  consensusIds: Set<number>
}) {
  const [view, setView] = useState<'list' | 'constellation'>('list')
  const [selected, setSelected] = useState<Recommendation | null>(null)
  const meta = PLATFORM_META[platform]

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex items-baseline justify-between gap-3 border-b border-hairline pb-2">
        <div
          className="flex items-baseline gap-2 overflow-hidden"
          title={query.data ? `config ${query.data.config_fingerprint}` : undefined}
        >
          <span className="size-2 shrink-0 rounded-full" style={{ background: `var(--data-${platform})` }} />
          <span className="text-sm font-medium">{meta.name}</span>
          <span className="hidden text-[10px] tracking-[0.18em] text-text-faint uppercase lg:inline">
            {meta.epithet}
          </span>
        </div>
        <div className="flex shrink-0 items-baseline gap-3">
          {query.data && (
            <span className="tnum font-mono text-xs text-text-dim">{query.data.timings.total_ms.toFixed(0)} ms</span>
          )}
          <div className="flex gap-2 text-xs">
            {(['list', 'constellation'] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={view === v ? 'text-accent' : 'text-text-faint hover:text-text-dim'}
              >
                {v === 'list' ? 'List' : 'Constellation'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {query.data && view === 'list' && <TimingStrip timings={query.data.timings} />}

      <div className="min-h-0 flex-1">
        {query.isError ? (
          <ErrorState error={query.error} platform={platform} />
        ) : !query.data ? (
          <Skeleton />
        ) : view === 'list' ? (
          <List
            recommendations={query.data.recommendations}
            hoveredId={hoveredId}
            onHover={onHover}
            consensusIds={consensusIds}
            explainOn={explainOn}
            onSelectPath={(rec) => {
              setSelected(rec)
              setView('constellation')
            }}
          />
        ) : (
          <Constellation
            recommendations={query.data.recommendations}
            seedKey={seedKey}
            platform={platform}
            explainOn={explainOn}
            selectedPath={selected?.path ?? null}
            onClearSelection={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  )
}

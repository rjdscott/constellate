import * as Tooltip from '@radix-ui/react-tooltip'
import { useQueries } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import ResultsPane from '../components/playground/ResultsPane.tsx'
import { recommend, useItems, useSearchItems, useUserContext } from '../lib/api.ts'
import { tidyTitle } from '../lib/format.ts'
import { isPlatformId, PLATFORM_IDS, PLATFORM_META, type PlatformId } from '../lib/platforms.ts'
import type { PlaneName, RetrievalRequest } from '../lib/types.ts'
import { useDocumentTitle } from '../lib/useDocumentTitle.ts'

type Mode = 'seed' | 'user'
type MaxHops = 1 | 2 | 3

const ALL_PLANES: PlaneName[] = ['relational', 'vector', 'graph']
const HOPS: MaxHops[] = [1, 2, 3]

interface QueryState {
  mode: Mode
  seedId: number | null
  userId: number | null
  k: number
  maxHops: MaxHops
  planes: PlaneName[]
  explain: boolean
  platforms: PlatformId[]
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)))
}

/** All query-builder state lives in the URL so a playground query is a
 *  shareable link, not just a run result. */
function readState(params: URLSearchParams): QueryState {
  const mode: Mode = params.get('mode') === 'user' ? 'user' : 'seed'
  const kRaw = Number(params.get('k'))
  const hopsRaw = Number(params.get('hops')) as MaxHops
  const planesRaw = params.get('planes')
  const explainRaw = params.get('explain')
  // singular ?platform= is the overview stars' link-in param; ?platforms= is
  // this page's own multi-select once the user has touched it.
  const platformsRaw = params.get('platforms') ?? params.get('platform')

  const planes = planesRaw ? planesRaw.split(',').filter((p): p is PlaneName => ALL_PLANES.includes(p as PlaneName)) : ALL_PLANES
  const platforms = platformsRaw ? platformsRaw.split(',').filter(isPlatformId) : [...PLATFORM_IDS]

  // ids get the same finiteness guard as k/hops: "?seed=abc" is NaN,
  // "?seed=  " is 0 — both must degrade to "no seed", not auto-run
  const id = (raw: string | null): number | null => {
    const parsed = Number(raw)
    return raw && raw.trim() && Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
  }

  return {
    mode,
    seedId: id(params.get('seed')),
    userId: id(params.get('user')),
    k: Number.isFinite(kRaw) && kRaw > 0 ? clampInt(kRaw, 5, 50) : 20,
    maxHops: HOPS.includes(hopsRaw) ? hopsRaw : 2,
    planes: planes.length > 0 ? planes : ALL_PLANES,
    explain: explainRaw !== null ? explainRaw === '1' : mode === 'seed',
    platforms: platforms.length > 0 ? platforms : [...PLATFORM_IDS],
  }
}

function writeState(state: QueryState): URLSearchParams {
  const params = new URLSearchParams()
  params.set('mode', state.mode)
  if (state.seedId !== null) params.set('seed', String(state.seedId))
  if (state.userId !== null) params.set('user', String(state.userId))
  params.set('k', String(state.k))
  params.set('hops', String(state.maxHops))
  params.set('planes', state.planes.join(','))
  params.set('explain', state.explain ? '1' : '0')
  params.set('platforms', state.platforms.join(','))
  return params
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="flex rounded-sm border border-hairline p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 rounded-sm px-2 py-1 text-xs transition-colors duration-[var(--motion-fast)] ${
            value === opt.value ? 'bg-raised text-text' : 'text-text-faint hover:text-text-dim'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] tracking-[0.16em] text-text-faint uppercase">{label}</span>
      {children}
    </div>
  )
}

function SeedPicker({ seedId, onPick }: { seedId: number | null; onPick: (id: number | null) => void }) {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [closed, setClosed] = useState(false) // Escape dismisses without clearing the typed query
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 200)
    return () => clearTimeout(t)
  }, [query])
  const search = useSearchItems(debounced.trim().length >= 2 ? debounced : '')
  const selected = useItems(seedId !== null ? [seedId] : [])
  const results = search.data ?? []
  const open = !closed && debounced.trim().length >= 2 && results.length > 0

  if (seedId !== null) {
    const title = selected.data?.[0] ? tidyTitle(selected.data[0].title).title : `#${seedId}`
    return (
      <span className="flex w-fit items-center gap-2 rounded-full border border-hairline px-3 py-1 text-xs text-text">
        {title}
        <button type="button" onClick={() => onPick(null)} aria-label="Clear seed" className="text-text-faint hover:text-text">
          ✕
        </button>
      </span>
    )
  }

  function pick(index: number) {
    const item = results[index]
    if (!item) return
    onPick(item.item_id)
    setQuery('')
  }

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setActiveIndex(0)
          setClosed(false)
        }}
        onKeyDown={(e) => {
          if (!open) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActiveIndex((i) => Math.min(i + 1, results.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActiveIndex((i) => Math.max(i - 1, 0))
          } else if (e.key === 'Enter') {
            e.preventDefault()
            pick(activeIndex)
          } else if (e.key === 'Escape') {
            e.preventDefault()
            setClosed(true)
          }
        }}
        placeholder="Search a movie…"
        role="combobox"
        aria-expanded={open}
        aria-controls="seed-picker-listbox"
        aria-activedescendant={open ? `seed-picker-option-${activeIndex}` : undefined}
        className="w-full rounded-sm border border-hairline bg-transparent px-2.5 py-1.5 text-sm text-text placeholder:text-text-faint focus:border-text-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      />
      {open && (
        <ul
          id="seed-picker-listbox"
          role="listbox"
          className="absolute z-10 mt-1 max-h-64 w-full overflow-y-auto rounded-sm border border-hairline bg-surface shadow-[var(--shadow-2)]"
        >
          {results.map((item, index) => {
            const { title, year } = tidyTitle(item.title)
            return (
              <li key={item.item_id} id={`seed-picker-option-${index}`} role="option" aria-selected={index === activeIndex}>
                <button
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => pick(index)}
                  className={`flex w-full items-baseline justify-between gap-2 px-2.5 py-1.5 text-left text-sm ${
                    index === activeIndex ? 'bg-raised' : ''
                  }`}
                >
                  <span className="truncate text-text">
                    {title} {year && <span className="text-text-faint">{year}</span>}
                  </span>
                  <span className="tnum shrink-0 font-mono text-[10px] text-text-faint">
                    {item.popularity.toFixed(0)}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function UserPicker({ userId, onChange }: { userId: number | null; onChange: (id: number | null) => void }) {
  const [toValidate, setToValidate] = useState<number | null>(null)
  const validation = useUserContext(toValidate)
  return (
    <div>
      <input
        type="number"
        min={1}
        value={userId ?? ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        onBlur={() => setToValidate(userId)}
        placeholder="User id"
        className="w-full rounded-sm border border-hairline bg-transparent px-2.5 py-1.5 text-sm text-text placeholder:text-text-faint focus:border-text-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      />
      {toValidate !== null && toValidate === userId && (
        <p className="mt-1 text-xs">
          {validation.data && <span className="text-text-dim">{validation.data.n_ratings} ratings</span>}
          {validation.isError && <span className="text-error">no ratings for user {toValidate}</span>}
        </p>
      )}
    </div>
  )
}

export default function Playground() {
  useDocumentTitle('Playground')
  const [searchParams, setSearchParams] = useSearchParams()
  const state = useMemo(() => readState(searchParams), [searchParams])
  const update = useCallback(
    (patch: Partial<QueryState>) => setSearchParams(writeState({ ...state, ...patch }), { replace: true }),
    [state, setSearchParams],
  )

  const [hoveredId, setHoveredId] = useState<number | null>(null)
  const [runId, setRunId] = useState(0)
  const [submitted, setSubmitted] = useState<{ request: RetrievalRequest; platforms: PlatformId[] } | null>(null)

  const canRun = (state.mode === 'seed' ? state.seedId !== null : state.userId !== null) && state.platforms.length > 0

  const run = useCallback(() => {
    if (!canRun) return
    const request: RetrievalRequest = {
      k: state.k,
      max_hops: state.maxHops,
      explain: state.explain,
      planes: state.planes.length === ALL_PLANES.length ? null : state.planes,
      ...(state.mode === 'seed' ? { seed_item_id: state.seedId } : { user_id: state.userId }),
    }
    setSubmitted({ request, platforms: state.platforms })
    setRunId((id) => id + 1)
  }, [state, canRun])

  // Arriving on a shareable link that already names a subject runs once.
  useEffect(() => {
    if (submitted === null && canRun) run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault()
        run()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [run])

  const queries = useQueries({
    queries: (submitted?.platforms ?? []).map((platform) => ({
      queryKey: ['playground', platform, runId],
      queryFn: () => recommend(submitted!.request, platform),
      enabled: submitted !== null,
      retry: 1,
    })),
  })
  const running = submitted !== null && queries.some((q) => q.isFetching)

  const consensusIds = useMemo(() => {
    const settled = queries.filter((q) => q.data)
    if (submitted === null || settled.length < submitted.platforms.length) return new Set<number>()
    const sets = settled.map((q) => new Set(q.data!.recommendations.map((r) => r.item_id)))
    const [first, ...rest] = sets
    return new Set([...first].filter((id) => rest.every((s) => s.has(id))))
  }, [queries, submitted])

  const seedKey = state.mode === 'seed' ? `item:${state.seedId}` : `user:${state.userId}`

  function togglePlane(plane: PlaneName) {
    const has = state.planes.includes(plane)
    if (has && state.planes.length === 1) return // ≥1 plane required
    update({ planes: has ? state.planes.filter((p) => p !== plane) : [...state.planes, plane] })
  }

  function togglePlatform(platform: PlatformId) {
    const has = state.platforms.includes(platform)
    if (has && state.platforms.length === 1) return // ≥1 platform required
    update({ platforms: has ? state.platforms.filter((p) => p !== platform) : [...state.platforms, platform] })
  }

  return (
    // Shell.tsx already renders one Tooltip.Provider app-wide.
    <>
      <div className="flex min-h-full">
        <aside className="flex w-[320px] shrink-0 flex-col gap-5 border-r border-hairline bg-surface p-6">
          <Field label="Query">
            <SegmentedControl
              options={[
                { value: 'user' as Mode, label: 'For a user' },
                { value: 'seed' as Mode, label: 'From a seed movie' },
              ]}
              value={state.mode}
              onChange={(mode) => update({ mode, explain: state.explain })}
            />
          </Field>

          {state.mode === 'seed' ? (
            <Field label="Seed movie">
              <SeedPicker seedId={state.seedId} onPick={(seedId) => update({ seedId })} />
            </Field>
          ) : (
            <Field label="User">
              <UserPicker userId={state.userId} onChange={(userId) => update({ userId })} />
            </Field>
          )}

          <Field label={`k · ${state.k}`}>
            <input
              type="range"
              min={5}
              max={50}
              value={state.k}
              onChange={(e) => update({ k: Number(e.target.value) })}
              className="accent-accent w-full"
            />
          </Field>

          <Field label="Max hops">
            <div className="flex gap-1.5">
              {HOPS.map((hops) => {
                const button = (
                  <button
                    key={hops}
                    type="button"
                    onClick={() => update({ maxHops: hops })}
                    className={`flex-1 rounded-sm border px-2 py-1 text-xs ${
                      state.maxHops === hops ? 'border-accent text-accent' : 'border-hairline text-text-dim hover:border-text-faint'
                    }`}
                  >
                    {hops}
                  </button>
                )
                if (hops !== 3) return button
                return (
                  <Tooltip.Root key={hops}>
                    <Tooltip.Trigger asChild>{button}</Tooltip.Trigger>
                    <Tooltip.Portal>
                      <Tooltip.Content
                        side="top"
                        className="max-w-[220px] rounded-sm border border-hairline bg-raised px-2 py-1 text-xs text-text-dim shadow-[var(--shadow-2)]"
                      >
                        3 hops · hub nodes fan out fast, latency grows with them
                      </Tooltip.Content>
                    </Tooltip.Portal>
                  </Tooltip.Root>
                )
              })}
            </div>
          </Field>

          <Field label="Planes">
            <div className="flex flex-col gap-1.5">
              {ALL_PLANES.map((plane) => (
                <label key={plane} className="flex cursor-pointer items-center gap-2 text-sm text-text-dim">
                  <input
                    type="checkbox"
                    checked={state.planes.includes(plane)}
                    onChange={() => togglePlane(plane)}
                    className="sr-only"
                  />
                  <span
                    className="size-3 rounded-sm border border-hairline"
                    style={{ background: state.planes.includes(plane) ? `var(--data-${plane})` : 'transparent' }}
                  />
                  {plane}
                </label>
              ))}
            </div>
          </Field>

          <Field label="Explain">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-text-dim">
              <input
                type="checkbox"
                checked={state.explain}
                onChange={(e) => update({ explain: e.target.checked })}
                className="sr-only"
              />
              <span
                className="flex h-4 w-7 items-center rounded-full border border-hairline px-0.5"
                style={{ background: state.explain ? 'var(--color-accent)' : 'transparent' }}
              >
                <span
                  className="size-2.5 rounded-full bg-text transition-transform duration-[var(--motion-fast)]"
                  style={{ transform: state.explain ? 'translateX(11px)' : 'translateX(0)' }}
                />
              </span>
              feeds the constellation
            </label>
          </Field>

          <Field label="Platforms">
            <div className="flex flex-wrap gap-1.5">
              {PLATFORM_IDS.map((platform) => {
                const active = state.platforms.includes(platform)
                return (
                  <button
                    key={platform}
                    type="button"
                    onClick={() => togglePlatform(platform)}
                    className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
                      active ? 'border-accent text-text' : 'border-hairline text-text-faint hover:text-text-dim'
                    }`}
                  >
                    <span className="size-1.5 rounded-full" style={{ background: `var(--data-${platform})` }} />
                    {PLATFORM_META[platform].name}
                  </button>
                )
              })}
            </div>
          </Field>

          <button
            type="button"
            disabled={!canRun}
            onClick={run}
            className="mt-2 flex items-center justify-center gap-2 rounded-sm bg-accent px-4 py-2.5 text-[11px] font-medium tracking-[0.18em] text-accent-contrast uppercase transition-opacity duration-[var(--motion-fast)] hover:opacity-85 disabled:opacity-40"
          >
            {running && (
              <svg viewBox="0 0 16 16" className="spinner size-3.5" fill="none" aria-hidden>
                <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            )}
            {running ? 'Running' : 'Run'}
            <span className="text-[10px] font-normal normal-case text-accent-contrast/60">
              {navigator.platform.toLowerCase().includes('mac') ? '⌘ Enter' : 'Ctrl Enter'}
            </span>
          </button>
        </aside>

        <section className="min-w-0 flex-1 overflow-x-auto p-6">
          {submitted === null ? (
            <p className="text-sm text-text-dim">Pick a seed movie or a user, then run.</p>
          ) : (
            <div
              className="grid h-full gap-8"
              style={{ gridTemplateColumns: `repeat(${submitted.platforms.length}, minmax(280px, 1fr))` }}
            >
              {submitted.platforms.map((platform, i) => (
                <ResultsPane
                  key={`${platform}-${runId}`}
                  platform={platform}
                  query={queries[i]}
                  seedKey={seedKey}
                  explainOn={submitted.request.explain ?? false}
                  hoveredId={hoveredId}
                  onHover={setHoveredId}
                  consensusIds={consensusIds}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  )
}

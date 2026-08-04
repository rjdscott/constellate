import { useQueries } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import Starfield from '../components/Starfield.tsx'
import { recommend, usePlatforms } from '../lib/api.ts'
import { tidyTitle } from '../lib/format.ts'
import type { RetrievalResponse } from '../lib/types.ts'

/* Chart coordinates live in a 1000×640 viewBox drawn edge-to-edge behind the
   content — a star atlas plate, not a diagram in a card. The asterism is
   deliberately irregular: real constellations aren't equilateral. */
const PLATFORMS = [
  { id: 'lyra', name: 'Lyra', epithet: 'embedded', sub: 'in-process · one artifact', x: 380, y: 150, side: -1 },
  { id: 'orion', name: 'Orion', epithet: 'unified', sub: 'one postgres · every plane', x: 760, y: 105, side: 1 },
  { id: 'hydra', name: 'Hydra', epithet: 'composed', sub: 'dedicated engines · projections', x: 615, y: 350, side: 1 },
]

/* Faint companion stars continue the asterism lines past the platforms —
   chart furniture, nothing more. */
const MINOR = [
  { x: 210, y: 92 },
  { x: 292, y: 260 },
  { x: 905, y: 210 },
  { x: 700, y: 470 },
  { x: 470, y: 452 },
]

/* Seeds for the live proof — ids verified against /v1/search/items. */
const SEEDS = [
  { id: 2571, title: 'The Matrix' },
  { id: 1, title: 'Toy Story' },
  { id: 541, title: 'Blade Runner' },
  { id: 1213, title: 'Goodfellas' },
  { id: 5618, title: 'Spirited Away' },
]

/** Four-point chart star: long thin spikes, the way atlases mark magnitude. */
const STAR = 'M0 -10 L1.7 -1.7 L10 0 L1.7 1.7 L0 10 L-1.7 1.7 L-10 0 L-1.7 -1.7 Z'

/** The thesis, demonstrated: one graph query, three platforms, four engines —
 *  the identical answer arrives at different speeds. Numbers alone don't land
 *  with strangers; watching three engines agree does. */
function ProofStrip() {
  const [seed, setSeed] = useState(SEEDS[0])
  const results = useQueries({
    queries: PLATFORMS.map((platform) => ({
      queryKey: ['proof', platform.id, seed.id],
      queryFn: () =>
        recommend({ seed_item_id: seed.id, k: 3, planes: ['graph'] }, platform.id),
      staleTime: Infinity,
      retry: 1,
    })),
  })
  const settled = results.filter((r) => r.data).map((r) => (r.data as RetrievalResponse))
  const agree =
    settled.length === PLATFORMS.length &&
    settled.every(
      (response) =>
        response.recommendations.map((rec) => rec.item_id).join() ===
        settled[0].recommendations.map((rec) => rec.item_id).join(),
    )

  return (
    <div className="mt-12 max-w-[880px] border-t border-hairline pt-6">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <p className="text-[11px] tracking-[0.24em] text-text-faint uppercase">
          Live proof · same question, three platforms
        </p>
        <div className="flex flex-wrap gap-2">
          {SEEDS.map((candidate) => (
            <button
              key={candidate.id}
              type="button"
              onClick={() => setSeed(candidate)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors duration-[var(--motion-fast)] ${
                candidate.id === seed.id
                  ? 'border-accent text-accent'
                  : 'border-hairline text-text-dim hover:border-text-faint hover:text-text'
              }`}
            >
              {candidate.title}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-8 sm:grid-cols-3">
        {PLATFORMS.map((platform, index) => {
          const query = results[index]
          return (
            <div key={platform.id}>
              <div className="flex items-baseline justify-between">
                <span
                  className="text-[11px] font-medium tracking-[0.22em] uppercase"
                  style={{ color: `var(--data-${platform.id})` }}
                >
                  {platform.name}
                </span>
                <span className="tnum font-mono text-xs text-text-faint">
                  {query.data ? `${query.data.timings.total_ms.toFixed(0)} ms` : ''}
                </span>
              </div>
              <ol className="mt-2.5 flex flex-col gap-2">
                {query.data
                  ? query.data.recommendations.map((rec, rank) => {
                      const { title, year } = tidyTitle(String(rec.metadata.title ?? rec.item_id))
                      return (
                        <li
                          key={rec.item_id}
                          className="proof-arrive flex gap-2.5 text-[13px] leading-snug"
                          style={{ animationDelay: `calc(${rank * 60}ms)` }}
                        >
                          <span className="tnum font-mono text-xs text-text-faint">{rank + 1}</span>
                          <span className="text-text">
                            {title}
                            {year && <span className="ml-1.5 text-text-faint">{year}</span>}
                          </span>
                        </li>
                      )
                    })
                  : query.isError
                    ? [
                        <li key="err" className="text-xs text-text-faint">
                          offline · start the API to run the proof
                        </li>,
                      ]
                    : [0, 1, 2].map((row) => (
                        <li key={row} className="h-[18px] w-3/4 animate-pulse rounded-sm bg-raised" />
                      ))}
              </ol>
            </div>
          )
        })}
      </div>

      <p className="mt-5 text-xs text-text-dim">
        {agree ? (
          <>
            <span className="text-accent">✦</span> Identical ranking, three engine stacks · R@10{' '}
            <span className="tnum font-mono">0.0965</span> on all four graph engines · hybrid beats
            vector <span className="tnum font-mono">p = 0.0038</span> · equivalence{' '}
            <span className="tnum font-mono">± 0.02</span>
          </>
        ) : (
          <>Server-side timings, illustrative. The benchmark harness is the citable source.</>
        )}
      </p>
    </div>
  )
}

function Status({ alive, fingerprint }: { alive: boolean | undefined; fingerprint: string | null }) {
  if (alive === undefined)
    return <tspan className="fill-text-faint">· · ·</tspan>
  if (!alive) return <tspan className="fill-text-faint">offline</tspan>
  return (
    <>
      <tspan className="fill-ok">●</tspan>
      <tspan dx="6" className="fill-text-faint">
        {fingerprint ?? ''}
      </tspan>
    </>
  )
}

export default function Overview() {
  const navigate = useNavigate()
  const platforms = usePlatforms()
  const asterism = PLATFORMS.map((p) => `${p.x} ${p.y}`).join(' L')

  return (
    <div className="relative min-h-full overflow-hidden">
      <div aria-hidden className="aurora pointer-events-none absolute inset-0" />
      <Starfield />

      {/* The plate: full-bleed, content overlays it lower-left. */}
      <svg
        viewBox="0 0 1000 640"
        preserveAspectRatio="xMidYMin meet"
        aria-label="The three Constellate platforms"
        role="img"
        className="pointer-events-none absolute inset-x-0 top-0 mx-auto h-auto w-full max-w-[1200px]"
      >
        {/* asterism */}
        <path d={`M${asterism} Z`} className="stroke-hairline" strokeWidth="1" fill="none" />
        <g className="stroke-hairline" strokeWidth="0.75" opacity="0.7">
          <path d={`M${MINOR[0].x} ${MINOR[0].y} L${PLATFORMS[0].x} ${PLATFORMS[0].y}`} />
          <path d={`M${MINOR[1].x} ${MINOR[1].y} L${PLATFORMS[0].x} ${PLATFORMS[0].y}`} />
          <path d={`M${MINOR[2].x} ${MINOR[2].y} L${PLATFORMS[1].x} ${PLATFORMS[1].y}`} />
          <path d={`M${MINOR[3].x} ${MINOR[3].y} L${PLATFORMS[2].x} ${PLATFORMS[2].y}`} />
          <path d={`M${MINOR[4].x} ${MINOR[4].y} L${PLATFORMS[2].x} ${PLATFORMS[2].y}`} />
        </g>
        {MINOR.map((m) => (
          <circle key={`${m.x}:${m.y}`} cx={m.x} cy={m.y} r="1.6" className="fill-text-faint" />
        ))}

        {PLATFORMS.map((platform) => {
          const status = platforms.data?.find((entry) => entry.platform === platform.id)
          const alive = platforms.isPending ? undefined : Boolean(status?.alive)
          return (
            <g
              key={platform.id}
              transform={`translate(${platform.x} ${platform.y})`}
              className="pointer-events-auto cursor-pointer"
              role="link"
              aria-label={`Open ${platform.name} in the playground`}
              tabIndex={0}
              onClick={() => void navigate(`/playground?platform=${platform.id}`)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void navigate(`/playground?platform=${platform.id}`)
              }}
              style={{ color: `var(--data-${platform.id})` }}
            >
              {/* chart marker: spiked star + fine halo ring, no blur clip-art */}
              <circle r="17" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.35" />
              <path d={STAR} fill="currentColor" />
              <circle r="26" fill="transparent" stroke="none" />

              <g
                transform={`translate(${30 * platform.side} -4)`}
                textAnchor={platform.side < 0 ? 'end' : 'start'}
              >
                <text className="fill-text" fontSize="24" fontWeight="550" letterSpacing="-0.01em">
                  {platform.name}
                </text>
                <text y="20" fontSize="10.5" letterSpacing="0.22em" className="fill-text-dim uppercase">
                  {platform.epithet}
                </text>
                <text y="38" fontSize="10" className="fill-text-faint">
                  {platform.sub}
                </text>
                <text y="56" fontSize="9.5" className="tnum font-mono">
                  <Status alive={alive} fingerprint={status?.config_fingerprint ?? null} />
                </text>
              </g>
            </g>
          )
        })}
      </svg>

      {/* The statement, lower-left — typography carries it, no cards. */}
      <div className="relative flex min-h-[calc(100vh-0px)] flex-col justify-end px-10 pb-12 pt-[420px] lg:px-14">
        <p className="flex items-center gap-3 text-[11px] tracking-[0.24em] text-text-faint uppercase">
          <span aria-hidden className="text-accent">✦</span>
          The knowledge-plane experiment
        </p>
        <h1 className="mt-4 max-w-[32ch] text-[clamp(34px,4vw,52px)] leading-[1.08] font-medium tracking-[-0.015em]">
          One retrieval contract.
          <br />
          Three platforms. Four engines.
          <br />
          Identical to four decimals.
        </h1>

        <ProofStrip />

        <div className="mt-10 flex items-center gap-4">
          <Link
            to="/playground"
            className="rounded-sm bg-accent px-4 py-2.5 text-[11px] font-medium tracking-[0.18em] text-accent-contrast uppercase transition-opacity duration-[var(--motion-fast)] hover:opacity-85"
          >
            Open playground
          </Link>
          <Link
            to="/bench"
            className="rounded-sm border border-hairline px-4 py-2.5 text-[11px] tracking-[0.18em] text-text-dim uppercase transition-colors duration-[var(--motion-fast)] hover:border-text-faint hover:text-text"
          >
            Benchmarks
          </Link>
        </div>
      </div>
    </div>
  )
}

/** p50 line + p95-p99 band per platform, across the harness's concurrency
 *  steps. Keys read: latency.runs[].{concurrency,percentiles_ms.p50/p95/p99}.
 *  The harness's last step at each concurrency is a capacity probe (higher
 *  rate_hz than the steady-state steps before it) — real data, kept in, log
 *  scale keeps it from swamping the steady-state points. */
import * as Plot from '@observablehq/plot'

import { PLATFORM_META } from '../../lib/platforms.ts'
import { cssVar } from '../../lib/theme.ts'
import type { LatencyRun } from '../../lib/types.ts'
import PlotFigure from './PlotFigure.tsx'
import { SECTION_OVERLINE, type PlatformArtifact } from './types.ts'

interface Row {
  platform: string
  color: string
  step: number
  p50: number
  p95: number
  p99: number
}

function stepLabels(runs: LatencyRun[]): string[] {
  const seen = new Map<number, number>()
  return runs.map((r) => {
    const n = (seen.get(r.concurrency) ?? 0) + 1
    seen.set(r.concurrency, n)
    return n > 1 ? `c${r.concurrency}⁺` : `c${r.concurrency}`
  })
}

function figure(loaded: PlatformArtifact[]) {
  return (width: number) => {
    const rows: Row[] = loaded.flatMap(({ platform, data }) =>
      !data
        ? []
        : data.latency.runs.map((run, step) => ({
            platform,
            color: cssVar(`--data-${platform}`),
            step,
            p50: run.percentiles_ms.p50,
            p95: run.percentiles_ms.p95,
            p99: run.percentiles_ms.p99,
          })),
    )
    const labelSource = loaded.find((a) => a.data)?.data?.latency.runs ?? []
    const labels = stepLabels(labelSource)
    const hairline = cssVar('--color-hairline')
    const lastByPlatform = new Map<string, Row>()
    for (const row of rows) lastByPlatform.set(row.platform, row) // runs in order → last write wins

    return Plot.plot({
      width,
      height: 260,
      marginRight: 60,
      style: {
        background: 'transparent',
        color: cssVar('--color-text-dim'),
        fontSize: '11px',
        fontFamily: 'var(--font-mono)',
      },
      x: { domain: labels.map((_, i) => i), tickFormat: (i: number) => labels[i] ?? '', label: 'concurrency' },
      y: { type: 'log', grid: true, label: 'ms', tickFormat: (v: number) => v.toLocaleString() },
      marks: [
        Plot.gridY({ stroke: hairline }),
        Plot.areaY(rows, { x: 'step', y1: 'p95', y2: 'p99', z: 'platform', fill: 'color', fillOpacity: 0.12 }),
        Plot.line(rows, { x: 'step', y: 'p50', z: 'platform', stroke: 'color', strokeWidth: 2 }),
        Plot.text([...lastByPlatform.values()], {
          x: 'step',
          y: 'p50',
          text: (d: Row) => `${PLATFORM_META[d.platform as keyof typeof PLATFORM_META].name} · ${d.p50.toFixed(0)}ms`,
          dx: 8,
          textAnchor: 'start',
          fill: 'color',
          fontSize: 11,
        }),
      ],
    })
  }
}

function Skeleton() {
  return <div className="h-[260px] animate-pulse rounded-sm bg-raised" />
}

export default function LatencySection({ artifacts }: { artifacts: PlatformArtifact[] }) {
  const loaded = artifacts.filter((a) => a.data)
  const stillLoading = artifacts.some((a) => a.isLoading)
  const allErrored = artifacts.length > 0 && artifacts.every((a) => a.isError)

  return (
    <section>
      <h2 className={SECTION_OVERLINE}>Latency</h2>
      {allErrored ? (
        <p className="mt-4 text-sm text-text-dim">Bench artifacts unavailable.</p>
      ) : stillLoading && loaded.length === 0 ? (
        <div className="mt-4">
          <Skeleton />
        </div>
      ) : (
        <div className="mt-4">
          <PlotFigure
            ariaLabel="p50 line, p95-p99 band, by concurrency step and platform"
            render={figure(loaded)}
            deps={[loaded.map((a) => a.data?.config_fingerprint).join()]}
            minHeight={260}
          />
          <p className="mt-2 text-xs text-text-faint">
            p50 line · p95-p99 band · log scale (⁺ = capacity-probe step, higher offered rate) ·{' '}
            {loaded[0]?.data?.latency_indicative ? 'indicative, not isolated hardware' : ''}
          </p>
        </div>
      )}
    </section>
  )
}

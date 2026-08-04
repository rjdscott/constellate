/** hybrid vs vector-only R@10 delta per platform. Keys read:
 *  quality.ablation_delta_hybrid_vs_vector.R@10,
 *  quality.significance.hybrid.comparisons.vector_only.recall@10 (p-value). */
import * as Plot from '@observablehq/plot'

import { PLATFORM_META } from '../../lib/platforms.ts'
import { cssVar } from '../../lib/theme.ts'
import PlotFigure from './PlotFigure.tsx'
import { SECTION_OVERLINE, type PlatformArtifact } from './types.ts'

interface Row {
  platform: string
  color: string
  label: string
  delta: number
}

function figure(loaded: PlatformArtifact[]) {
  return (width: number) => {
    const rows: Row[] = loaded.map(({ platform, data }) => ({
      platform,
      color: cssVar(`--data-${platform}`),
      label: PLATFORM_META[platform as keyof typeof PLATFORM_META].name,
      delta: data!.quality.ablation_delta_hybrid_vs_vector['R@10'],
    }))
    const hairline = cssVar('--color-hairline')
    return Plot.plot({
      width,
      height: 40 + rows.length * 44,
      marginLeft: 70,
      marginRight: 90,
      style: { background: 'transparent', color: cssVar('--color-text-dim'), fontSize: '11px' },
      x: { grid: true, label: 'Δ R@10 (hybrid − vector-only)', zero: true },
      y: { domain: rows.map((r) => r.label), label: null },
      marks: [
        Plot.gridX({ stroke: hairline }),
        Plot.ruleX([0], { stroke: hairline }),
        Plot.ruleY(rows, { y: 'label', x1: 0, x2: 'delta', stroke: 'color', strokeWidth: 1.5, opacity: 0.55 }),
        Plot.dot(rows, { x: 'delta', y: 'label', fill: 'color', r: 5 }),
        Plot.text(rows, {
          x: 'delta',
          y: 'label',
          text: (d: Row) => `+${d.delta.toFixed(4)}`,
          dx: 12,
          textAnchor: 'start',
          fill: 'color',
          fontSize: 11,
        }),
      ],
    })
  }
}

function Skeleton({ rows }: { rows: number }) {
  return <div className="animate-pulse rounded-sm bg-raised" style={{ height: 40 + rows * 44 }} />
}

export default function AblationSection({ artifacts }: { artifacts: PlatformArtifact[] }) {
  const loaded = artifacts.filter((a) => a.data)
  const stillLoading = artifacts.some((a) => a.isLoading)
  const allErrored = artifacts.length > 0 && artifacts.every((a) => a.isError)

  return (
    <section>
      <h2 className={SECTION_OVERLINE}>Ablation</h2>
      {allErrored ? (
        <p className="mt-4 text-sm text-text-dim">Bench artifacts unavailable.</p>
      ) : stillLoading && loaded.length === 0 ? (
        <div className="mt-4">
          <Skeleton rows={artifacts.length || 3} />
        </div>
      ) : (
        <>
          <div className="mt-4">
            <PlotFigure
              ariaLabel="hybrid vs vector-only R@10 delta by platform"
              render={figure(loaded)}
              deps={[loaded.map((a) => a.data?.config_fingerprint).join()]}
              minHeight={40 + loaded.length * 44}
            />
          </div>
          <ul className="mt-2 flex flex-col gap-1">
            {loaded.map(({ platform, data }) => (
              <li key={platform} className="text-xs text-text-dim">
                <span style={{ color: `var(--data-${platform})` }}>{PLATFORM_META[platform].name}</span> · p{' '}
                <span className="tnum font-mono">
                  {data!.quality.significance.hybrid.comparisons.vector_only['recall@10'].toExponential(2)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

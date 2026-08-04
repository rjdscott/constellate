/** R@10 / nDCG@10 per arm (vector_only / graph_only / hybrid) × platform.
 *  Keys read: quality.arms.<arm>.overall.{R@10,nDCG@10},
 *  quality.significance.hybrid.comparisons.vector_only.{recall@10,ndcg@10}. */
import * as Plot from '@observablehq/plot'

import { PLATFORM_META } from '../../lib/platforms.ts'
import { cssVar } from '../../lib/theme.ts'
import PlotFigure from './PlotFigure.tsx'
import { SECTION_OVERLINE, type PlatformArtifact } from './types.ts'

const ARMS = ['vector_only', 'graph_only', 'hybrid'] as const
const ARM_LABEL: Record<(typeof ARMS)[number], string> = {
  vector_only: 'vector',
  graph_only: 'graph',
  hybrid: 'hybrid',
}

interface Point {
  platform: string
  color: string
  arm: (typeof ARMS)[number]
  value: number
}

function metricFigure(loaded: PlatformArtifact[], metric: 'R@10' | 'nDCG@10') {
  return (width: number) => {
    const points: Point[] = loaded.flatMap(({ platform, data }) =>
      !data
        ? []
        : ARMS.map((arm) => ({
            platform,
            color: cssVar(`--data-${platform}`),
            arm,
            value: data.quality.arms[arm].overall[metric],
          })),
    )
    const hairline = cssVar('--color-hairline')
    return Plot.plot({
      width,
      height: 230,
      marginRight: 56,
      style: { background: 'transparent', color: cssVar('--color-text-dim'), fontSize: '11px' },
      x: { domain: ARMS, tickFormat: (a: string) => ARM_LABEL[a as (typeof ARMS)[number]], label: null },
      y: { grid: true, label: metric, zero: true, nice: true },
      marks: [
        Plot.gridY({ stroke: hairline }),
        Plot.ruleY([0], { stroke: hairline }),
        Plot.line(points, { x: 'arm', y: 'value', z: 'platform', stroke: 'color', strokeWidth: 1.5, opacity: 0.55 }),
        Plot.dot(points, { x: 'arm', y: 'value', fill: 'color', r: 4 }),
        Plot.text(
          points.filter((p) => p.arm === 'hybrid'),
          {
            x: 'arm',
            y: 'value',
            text: (d: Point) => PLATFORM_META[d.platform as keyof typeof PLATFORM_META].name,
            dx: 8,
            textAnchor: 'start',
            fill: 'color',
            fontSize: 11,
          },
        ),
      ],
    })
  }
}

function Skeleton() {
  return <div className="h-[230px] animate-pulse rounded-sm bg-raised" />
}

export default function QualitySection({ artifacts }: { artifacts: PlatformArtifact[] }) {
  const loaded = artifacts.filter((a) => a.data)
  const stillLoading = artifacts.some((a) => a.isLoading)
  const allErrored = artifacts.length > 0 && artifacts.every((a) => a.isError)

  // Headline: graph arm is byte-identical across platforms (same seeds, same
  // engine contract) — verified from the loaded artifacts themselves, not
  // hardcoded, so the claim only prints when it's true of what's on screen.
  const graphValues = loaded.map((a) => a.data!.quality.arms.graph_only.overall)
  const graphIdentical =
    graphValues.length > 1 && graphValues.every((v) => v['R@10'] === graphValues[0]['R@10'] && v['nDCG@10'] === graphValues[0]['nDCG@10'])

  return (
    <section>
      <h2 className={SECTION_OVERLINE}>Quality</h2>

      {allErrored ? (
        <p className="mt-4 text-sm text-text-dim">Bench artifacts unavailable.</p>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-1 gap-8 lg:grid-cols-2">
            {stillLoading && loaded.length === 0 ? (
              <>
                <Skeleton />
                <Skeleton />
              </>
            ) : (
              <>
                <PlotFigure
                  ariaLabel="R@10 by arm and platform"
                  render={metricFigure(loaded, 'R@10')}
                  deps={[loaded.map((a) => a.data?.config_fingerprint).join()]}
                />
                <PlotFigure
                  ariaLabel="nDCG@10 by arm and platform"
                  render={metricFigure(loaded, 'nDCG@10')}
                  deps={[loaded.map((a) => a.data?.config_fingerprint).join()]}
                />
              </>
            )}
          </div>

          {graphIdentical && (
            <p className="mt-4 text-xs text-text-dim">
              Graph arm identical across platforms · R@10{' '}
              <span className="tnum font-mono">{graphValues[0]['R@10'].toFixed(4)}</span> · nDCG@10{' '}
              <span className="tnum font-mono">{graphValues[0]['nDCG@10'].toFixed(4)}</span> on every engine.
            </p>
          )}

          <ul className="mt-2 flex flex-col gap-1">
            {loaded.map(({ platform, data }) => {
              const cmp = data!.quality.significance.hybrid.comparisons.vector_only
              return (
                <li key={platform} className="text-xs text-text-dim">
                  <span style={{ color: `var(--data-${platform})` }}>{PLATFORM_META[platform].name}</span> · hybrid
                  vs vector · p(R@10) <span className="tnum font-mono">{cmp['recall@10'].toExponential(2)}</span> ·
                  p(nDCG@10) <span className="tnum font-mono">{cmp['ndcg@10'].toExponential(2)}</span>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}

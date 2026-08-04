/** Not in the bench artifacts — engine_state only covers Qdrant's own point
 *  counts. These are the runbook-recorded operational figures
 *  (docs/runbooks/run-hydra.md#footprint), quoted rather than invented. */
import { SECTION_OVERLINE } from './types.ts'

const ROWS = [
  { platform: 'lyra', containers: '0 (in-process)', rss: '—', disk: '348 MB', load: 'n/a' },
  { platform: 'orion', containers: '1', rss: '794 MiB', disk: '6.8 GB', load: '25M interactions in 43s · ~90s fresh' },
  { platform: 'hydra', containers: '3', rss: '~2.27 GiB', disk: '~9.9 GB', load: '98.9s cold · rebuild 40.7–44.3s' },
] as const

export default function FootprintSection() {
  return (
    <section>
      <h2 className={SECTION_OVERLINE}>Footprint</h2>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-hairline text-[11px] tracking-[0.16em] text-text-faint uppercase">
              <th className="py-2 pr-4 font-normal">Platform</th>
              <th className="py-2 pr-4 font-normal">Containers</th>
              <th className="py-2 pr-4 font-normal">Idle RSS</th>
              <th className="py-2 pr-4 font-normal">On disk</th>
              <th className="py-2 font-normal">Load / rebuild</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.platform} className="border-b border-hairline last:border-0">
                <td className="py-2 pr-4">
                  <span className="flex items-center gap-2">
                    <span className="size-1.5 rounded-full" style={{ background: `var(--data-${row.platform})` }} />
                    {row.platform}
                  </span>
                </td>
                <td className="tnum py-2 pr-4 font-mono text-text-dim">{row.containers}</td>
                <td className="tnum py-2 pr-4 font-mono text-text-dim">{row.rss}</td>
                <td className="tnum py-2 pr-4 font-mono text-text-dim">{row.disk}</td>
                <td className="tnum py-2 font-mono text-text-dim">{row.load}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-text-faint">
        Measured 2026-08-04, post-load · source docs/runbooks/run-hydra.md#footprint
      </p>
    </section>
  )
}

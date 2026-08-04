import { PLATFORM_IDS, PLATFORM_META, type PlatformId } from '../../lib/platforms.ts'
import type { BenchResultEntry } from '../../lib/types.ts'

/** Per-platform artifact picker. One `<select>` per platform, latest-by-`utc`
 *  preselected by the caller (Bench.tsx) — this component is pure display +
 *  choice, no defaulting logic of its own. */
export default function ArtifactPicker({
  listing,
  selected,
  onSelect,
}: {
  listing: BenchResultEntry[]
  selected: Partial<Record<PlatformId, string>>
  onSelect: (platform: PlatformId, name: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4">
      {PLATFORM_IDS.map((platform) => {
        const entries = listing
          .filter((e) => e.platform === platform)
          .sort((a, b) => (b.utc ?? '').localeCompare(a.utc ?? ''))
        const current = entries.find((e) => e.name === selected[platform])
        return (
          <div key={platform} className="flex flex-col gap-1">
            <label
              htmlFor={`bench-artifact-${platform}`}
              className="flex items-center gap-1.5 text-[11px] tracking-[0.16em] text-text-faint uppercase"
            >
              <span className="size-1.5 rounded-full" style={{ background: `var(--data-${platform})` }} />
              {PLATFORM_META[platform].name}
            </label>
            {entries.length === 0 ? (
              <span className="text-xs text-text-faint">no artifacts</span>
            ) : (
              <select
                id={`bench-artifact-${platform}`}
                value={selected[platform] ?? ''}
                onChange={(e) => onSelect(platform, e.target.value)}
                className="rounded-sm border border-hairline bg-transparent px-2 py-1 text-xs text-text focus:border-text-faint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {entries.map((entry) => (
                  <option key={entry.name} value={entry.name}>
                    {entry.utc ? entry.utc.replace('T', ' ').replace('+00:00', 'Z') : entry.name}
                  </option>
                ))}
              </select>
            )}
            {current?.config_fingerprint && (
              <span className="tnum font-mono text-[10px] text-text-faint">{current.config_fingerprint}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

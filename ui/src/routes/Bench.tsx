import { useEffect, useState } from 'react'

import AblationSection from '../components/bench/AblationSection.tsx'
import ArtifactPicker from '../components/bench/ArtifactPicker.tsx'
import FootprintSection from '../components/bench/FootprintSection.tsx'
import LatencySection from '../components/bench/LatencySection.tsx'
import QualitySection from '../components/bench/QualitySection.tsx'
import type { PlatformArtifact } from '../components/bench/types.ts'
import { useBenchArtifacts, useBenchResults } from '../lib/api.ts'
import { PLATFORM_IDS, type PlatformId } from '../lib/platforms.ts'
import { useDocumentTitle } from '../lib/useDocumentTitle.ts'

export default function Bench() {
  useDocumentTitle('Bench')
  const listing = useBenchResults()
  const [selected, setSelected] = useState<Partial<Record<PlatformId, string>>>({})

  // Latest-by-utc preselect per platform, once the listing arrives. Never
  // overwrites a choice the visitor already made (picking an older artifact
  // and having it snap back to latest on refetch would be maddening).
  useEffect(() => {
    if (!listing.data) return
    setSelected((prev) => {
      let changed = false
      const next = { ...prev }
      for (const platform of PLATFORM_IDS) {
        if (next[platform]) continue
        const latest = listing.data
          .filter((e) => e.platform === platform)
          .sort((a, b) => (b.utc ?? '').localeCompare(a.utc ?? ''))[0]
        if (latest) {
          next[platform] = latest.name
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [listing.data])

  const names = PLATFORM_IDS.map((p) => selected[p])
  const queries = useBenchArtifacts(names)
  const artifacts: PlatformArtifact[] = PLATFORM_IDS.map((platform, i) => ({
    platform,
    data: queries[i]?.data,
    isLoading: queries[i]?.isLoading ?? false,
    isError: queries[i]?.isError ?? false,
  }))

  return (
    <section className="px-10 py-10 lg:px-14">
      <div className="border-b border-hairline pb-6">
        <p className="text-[11px] tracking-[0.24em] text-text-faint uppercase">Benchmark dashboards</p>
        <h1 className="mt-2 text-2xl font-medium tracking-[-0.015em]">
          One retrieval contract, three platforms, measured
        </h1>
        {listing.isError ? (
          <p className="mt-6 text-sm text-text-dim">Bench results unavailable.</p>
        ) : listing.isPending ? (
          <div className="mt-6 flex gap-8">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 w-32 animate-pulse rounded-sm bg-raised" />
            ))}
          </div>
        ) : (
          <div className="mt-6">
            <ArtifactPicker
              listing={listing.data}
              selected={selected}
              onSelect={(platform, name) => setSelected((prev) => ({ ...prev, [platform]: name }))}
            />
          </div>
        )}
      </div>

      <div className="mt-10 border-t border-hairline pt-8">
        <QualitySection artifacts={artifacts} />
      </div>
      <div className="mt-10 border-t border-hairline pt-8">
        <LatencySection artifacts={artifacts} />
      </div>
      <div className="mt-10 border-t border-hairline pt-8">
        <AblationSection artifacts={artifacts} />
      </div>
      <div className="mt-10 border-t border-hairline pt-8">
        <FootprintSection />
      </div>
    </section>
  )
}

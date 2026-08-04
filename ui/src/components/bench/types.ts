import type { PlatformId } from '../../lib/platforms.ts'
import type { BenchArtifact } from '../../lib/types.ts'

/** One selected artifact per platform, in whatever load state react-query has
 *  it in — every bench section renders straight off this, no section repeats
 *  the fetch. */
export interface PlatformArtifact {
  platform: PlatformId
  data: BenchArtifact | undefined
  isLoading: boolean
  isError: boolean
}

export const SECTION_OVERLINE = 'text-[11px] tracking-[0.24em] text-text-faint uppercase'

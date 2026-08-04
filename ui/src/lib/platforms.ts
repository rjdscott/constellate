/** Shared platform identity — query-builder chips and results-pane headers
 *  both need name/epithet, so it lives here rather than duplicated. Overview's
 *  own PLATFORMS array carries chart coordinates too and stays local to it. */

export const PLATFORM_IDS = ['lyra', 'orion', 'hydra'] as const
export type PlatformId = (typeof PLATFORM_IDS)[number]

export const PLATFORM_META: Record<PlatformId, { name: string; epithet: string }> = {
  lyra: { name: 'Lyra', epithet: 'embedded' },
  orion: { name: 'Orion', epithet: 'unified' },
  hydra: { name: 'Hydra', epithet: 'composed' },
}

export function isPlatformId(value: string): value is PlatformId {
  return (PLATFORM_IDS as readonly string[]).includes(value)
}

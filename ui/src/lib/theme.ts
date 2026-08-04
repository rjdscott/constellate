/** Shared by any component that reads CSS custom properties imperatively
 *  (Observable Plot charts, Cytoscape) — React state doesn't observe DOM
 *  attribute mutations on its own, so this bridges the theme toggle
 *  (`html[data-theme]`, set by `app/Shell.tsx`) into a re-render. */
import { useEffect, useState } from 'react'

export function useThemeVersion(): number {
  const [version, setVersion] = useState(0)
  useEffect(() => {
    const observer = new MutationObserver(() => setVersion((v) => v + 1))
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return version
}

/** Same pattern as Constellation.tsx's cssVar — kept local there since it
 *  predates this file; charts import this one instead of duplicating it. */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

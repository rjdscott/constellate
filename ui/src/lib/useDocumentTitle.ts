import { useEffect } from 'react'

/** index.html sets the bare 'Constellate' title; each route appends its own
 *  section so back/forward history and browser tabs read sensibly. */
export function useDocumentTitle(section: string): void {
  useEffect(() => {
    const previous = document.title
    document.title = `Constellate · ${section}`
    return () => {
      document.title = previous
    }
  }, [section])
}

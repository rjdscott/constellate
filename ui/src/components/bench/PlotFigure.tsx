/** One Observable Plot figure, theme-aware and responsive. Colors are read
 *  from CSS custom properties inside `render` at draw time — Plot renders to
 *  a detached SVG, outside Tailwind's cascade, so tokens must be resolved
 *  imperatively (same reasoning as Constellation.tsx's cssVar/cytoscape). Redraws
 *  on container resize and on `html[data-theme]` change (useThemeVersion). */
import { useEffect, useRef, useState } from 'react'

import { useThemeVersion } from '../../lib/theme.ts'

export default function PlotFigure({
  render,
  deps = [],
  ariaLabel,
  minHeight = 220,
}: {
  render: (width: number) => (SVGSVGElement | HTMLElement) & { remove(): void }
  deps?: unknown[]
  ariaLabel: string
  minHeight?: number
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const themeVersion = useThemeVersion()
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) setWidth(Math.round(w))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el || width === 0) return
    const figure = render(width)
    el.replaceChildren(figure)
    return () => figure.remove()
    // deps drives redraw; render is re-created by the caller each time its own inputs change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, themeVersion, ...deps])

  return <div ref={containerRef} role="img" aria-label={ariaLabel} style={{ minHeight }} />
}

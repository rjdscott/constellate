import { useEffect, useRef } from 'react'

const STAR_COUNT = 260
const SEED = 0x5eed1e

/** mulberry32 — same sky on every load, every machine, every screenshot. */
function prng(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/**
 * Static seeded starfield — the one piece of pure atmosphere the design system
 * permits (design/README.md). Drawn once per size change, never animated, and
 * hidden in light theme by the `.starfield` rule in index.css.
 */
export default function Starfield() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const draw = () => {
      const { clientWidth: width, clientHeight: height } = canvas
      if (!width || !height) return // hidden (light theme) — nothing to draw
      const dpr = window.devicePixelRatio || 1
      canvas.width = width * dpr
      canvas.height = height * dpr
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      ctx.fillStyle = getComputedStyle(canvas).color // --color-text via `text-text`
      const random = prng(SEED)
      for (let i = 0; i < STAR_COUNT; i++) {
        const x = random() * width
        const y = random() * height
        // magnitude distribution: mostly dust, a scatter of brighter points —
        // per-star ceiling and field character set in design/README.md
        const bright = random()
        const radius = 0.3 + bright * 0.9
        ctx.globalAlpha = 0.04 + bright * bright * 0.2
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    const observer = new ResizeObserver(draw)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  return (
    <canvas
      ref={ref}
      aria-hidden
      className="starfield pointer-events-none absolute inset-0 size-full text-text"
    />
  )
}

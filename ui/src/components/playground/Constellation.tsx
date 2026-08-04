import * as Dialog from '@radix-ui/react-dialog'
import cytoscape from 'cytoscape'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { similar, useItems, useTags } from '../../lib/api.ts'
import { tidyTitle } from '../../lib/format.ts'
import { humanizeEdgeType, parsePath, type PathNode } from '../../lib/paths.ts'
import type { Recommendation } from '../../lib/types.ts'

type Core = cytoscape.Core
type ElementDefinition = cytoscape.ElementDefinition
type NodeSingular = cytoscape.NodeSingular

/** Tokens are read at runtime (same pattern as Shell.tsx's motionSeconds) so
 *  colours stay theme-correct without hardcoding hex in a stylesheet cytoscape
 *  owns outside Tailwind's reach. */
function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function motionMs(token: string): number {
  return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(token)) || 0
}

interface Expansion {
  seedKey: string
  label: string
  recommendations: Recommendation[]
}

interface GraphData {
  elements: ElementDefinition[]
  movieIds: number[]
  tagIds: string[]
  hasAnyPath: boolean
}

/** Union of every recommendation's path, deduped by node/edge key — the
 *  constellation IS the graph of everything the response explained. */
const ALWAYS_LABELED_RANKS = 8

export function buildGraph(
  seedKey: string,
  recommendationSets: Recommendation[][],
  itemTitles: Map<number, string> = new Map(),
  tagNames: Record<string, string> = {},
): GraphData {
  const nodes = new Map<string, PathNode>()
  const edges = new Map<string, { source: string; target: string; edgeType: string }>()
  let hasAnyPath = false

  // Top ranks of the primary response keep permanent labels; everything else
  // labels on hover — twenty overlapping titles is soup, not a star chart.
  const bestRank = new Map<string, number>()
  for (const rec of recommendationSets[0] ?? []) {
    bestRank.set(`item:${rec.item_id}`, rec.rank)
  }

  for (const recs of recommendationSets) {
    for (const rec of recs) {
      const parsed = parsePath(rec.path)
      if (!parsed) continue
      hasAnyPath = true
      for (const node of parsed.nodes) nodes.set(node.key, node)
      for (let i = 0; i < parsed.edgeTypes.length; i++) {
        const source = parsed.nodes[i].key
        const target = parsed.nodes[i + 1].key
        const edgeType = parsed.edgeTypes[i]
        edges.set(`${source}>${target}>${edgeType}`, { source, target, edgeType })
      }
    }
  }

  // hop = shortest distance from the primary response's path roots, relaxed
  // to a fixpoint over the WHOLE union — a one-pass walk froze descendants
  // at stale rings when a later expansion found a shortcut to their parent.
  const hops = new Map<string, number>()
  for (const rec of recommendationSets[0] ?? []) {
    const parsed = parsePath(rec.path)
    if (parsed) hops.set(parsed.nodes[0].key, 0)
  }
  let changed = true
  while (changed) {
    changed = false
    for (const edge of edges.values()) {
      const dist = hops.get(edge.source)
      if (dist !== undefined && (hops.get(edge.target) ?? Infinity) > dist + 1) {
        hops.set(edge.target, dist + 1)
        changed = true
      }
    }
  }

  const movieIds: number[] = []
  const tagIds: string[] = []
  const elements: ElementDefinition[] = []
  for (const node of nodes.values()) {
    const hop = hops.get(node.key) ?? 0
    if (node.kind === 'movie') movieIds.push(Number(node.id))
    if (node.kind === 'tag') tagIds.push(node.id)
    const label =
      node.kind === 'movie'
        ? (itemTitles.get(Number(node.id)) && tidyTitle(itemTitles.get(Number(node.id))!).title) || `#${node.id}`
        : node.kind === 'user'
          ? `user ${node.id}`
          : node.kind === 'tag'
            ? (tagNames[node.id] ?? `tag ${node.id}`)
            : node.id // genre: key suffix, no lookup
    const isSeed = node.key === seedKey
    const showLabel =
      isSeed ||
      node.kind !== 'movie' ||
      (bestRank.get(node.key) ?? Infinity) <= ALWAYS_LABELED_RANKS
    elements.push({
      data: { id: node.key, kind: node.kind, label, hop, showLabel, isSeed },
      classes: isSeed ? 'seed' : undefined,
    })
  }
  for (const [id, edge] of edges) {
    elements.push({ data: { id, source: edge.source, target: edge.target, edgeType: edge.edgeType } })
  }
  return { elements, movieIds, tagIds, hasAnyPath }
}

const STYLE: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      'background-color': cssVar('--color-text-faint'),
      label: '',
      color: cssVar('--color-text-dim'),
      'font-family': cssVar('--font-mono'),
      'font-size': 11,
      'text-wrap': 'ellipsis',
      'text-max-width': '130px',
      'text-valign': 'bottom',
      'text-margin-y': 6,
      width: 'data(radius)',
      height: 'data(radius)',
      'border-width': 0,
      'border-color': cssVar('--color-accent'),
      'overlay-opacity': 0,
      'transition-property': 'opacity',
      'transition-duration': 200,
    },
  },
  {
    selector: 'node[kind="movie"]',
    style: {
      'background-color': cssVar('--color-text'),
      color: cssVar('--color-text'),
      'font-family': cssVar('--font-sans'),
      'font-size': 12,
    },
  },
  { selector: 'node[kind="user"]', style: { 'background-color': cssVar('--data-lyra') } },
  { selector: 'node[kind="tag"]', style: { 'background-color': cssVar('--data-hydra') } },
  { selector: 'node[kind="genre"]', style: { 'background-color': cssVar('--data-orion') } },
  { selector: 'node[?showLabel]', style: { label: 'data(label)' } },
  { selector: 'node.hover-label', style: { label: 'data(label)' } },
  { selector: 'node.seed', style: { 'border-width': 2 } },
  { selector: 'node.selected-target', style: { 'border-width': 3 } },
  { selector: 'node.entering', style: { opacity: 0 } },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': cssVar('--color-hairline'),
      'curve-style': 'bezier',
      opacity: 0.6,
      label: 'data(hoverLabel)',
      color: cssVar('--color-text-faint'),
      'font-family': cssVar('--font-mono'),
      'font-size': 9,
      'text-rotation': 'autorotate',
    },
  },
  { selector: 'edge.path-edge', style: { 'line-color': cssVar('--color-accent'), width: 2, opacity: 1 } },
  { selector: '.dimmed', style: { opacity: 0.35 } },
]

function clampRadius(degree: number): number {
  return Math.min(28, Math.max(12, 12 + degree * 3))
}

function GraphCanvas({
  elements,
  seedKey,
  selectedPath,
  onExpand,
  onClearSelection,
  isFullscreen,
  onToggleFullscreen,
}: {
  elements: ElementDefinition[]
  seedKey: string
  selectedPath: string[] | null
  onExpand: (nodeKey: string) => void
  onClearSelection: () => void
  isFullscreen: boolean
  onToggleFullscreen: () => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const onExpandRef = useRef(onExpand)
  onExpandRef.current = onExpand
  const onClearRef = useRef(onClearSelection)
  onClearRef.current = onClearSelection

  // Mount once per container instance (fresh on every fullscreen toggle —
  // camera position resets, graph data does not, since elements/expansions
  // live in the parent).
  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      style: STYLE,
      elements: [],
      wheelSensitivity: 0.2,
    })
    cyRef.current = cy
    cy.on('tap', 'node[kind="movie"]', (evt) => onExpandRef.current(evt.target.id()))
    cy.on('tap', (evt) => {
      if (evt.target === cy) onClearRef.current()
    })
    // Cytoscape caches container dimensions at init — a flex pane that settles
    // (or a view toggle that mounts at zero height) leaves the graph fitted to
    // a stale box. ponytail: refit on every container resize; loses manual
    // zoom on window resize, acceptable until someone complains.
    const observer = new ResizeObserver(() => {
      cy.resize()
      cy.fit(undefined, 24)
    })
    observer.observe(containerRef.current)
    return () => {
      observer.disconnect()
      cy.destroy()
      cyRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Topology sync: add new elements, drop stale ones, relayout. New nodes
  // start dimmed via .entering then fade in (transition-property above).
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    const nextIds = new Set(elements.map((e) => e.data.id))
    const removed = cy.elements().filter((ele) => !nextIds.has(ele.id()))
    removed.remove()
    const existingIds = new Set(cy.elements().map((ele) => ele.id()))
    const additions = elements.filter((e) => !existingIds.has(e.data.id as string))
    const addedNodeIds = additions.filter((e) => !('source' in e.data)).map((e) => e.data.id as string)
    if (additions.length > 0) {
      cy.add(additions)
      cy.nodes()
        .filter((n) => addedNodeIds.includes(n.id()))
        .addClass('entering')
    }

    // Labels/hops resolve async (titles and tag names arrive after the graph's
    // first paint) — patch them onto already-existing nodes every render, since
    // the add/remove diff above only touches nodes whose id just entered or left.
    for (const e of elements) {
      if ('source' in e.data) continue
      const node = cy.getElementById(e.data.id as string)
      if (!node.length) continue
      for (const key of ['label', 'hop', 'showLabel'] as const) {
        if (node.data(key) !== e.data[key]) node.data(key, e.data[key])
      }
    }
    cy.nodes().forEach((n: NodeSingular) => {
      n.data('radius', clampRadius(n.degree(false)))
    })

    // Only re-run the layout when the graph's shape actually changed — a
    // label resolving shouldn't re-animate/re-fit the whole constellation.
    if ((additions.length > 0 || removed.length > 0) && elements.length > 0) {
      // Concentric wheel: seed at the center, each hop on its own ring — the
      // star-chart read. Breadthfirst rendered the same data as a flat fan.
      const maxHop = Math.max(0, ...cy.nodes().map((n) => Number(n.data('hop')) || 0))
      const layout = cy.layout({
        name: 'concentric',
        concentric: (n) => maxHop - (Number(n.data('hop')) || 0),
        levelWidth: () => 1,
        minNodeSpacing: 18,
        animate: motionMs('--motion-base') > 0,
        animationDuration: motionMs('--motion-base'),
        fit: true,
        padding: 24,
      })
      layout.one('layoutstop', () => {
        cy.nodes()
          .filter((n) => addedNodeIds.includes(n.id()))
          .removeClass('entering')
        // ponytail: `fit` inside animated breadthfirst layouts is unreliable
        // (cytoscape#2652-style flakiness) — a follow-up manual fit is cheap
        // insurance so the graph never renders pinned in a corner.
        cy.fit(undefined, 24)
      })
      layout.run()
    }
  }, [elements, seedKey])

  // Hover-only labels (no permanent clutter): edge types, and titles for the
  // movies outside the always-labeled top ranks.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    const onOver = (evt: cytoscape.EventObject) => {
      evt.target.data('hoverLabel', humanizeEdgeType(evt.target.data('edgeType')))
    }
    const onOut = (evt: cytoscape.EventObject) => evt.target.data('hoverLabel', '')
    const onNodeOver = (evt: cytoscape.EventObject) => evt.target.addClass('hover-label')
    const onNodeOut = (evt: cytoscape.EventObject) => evt.target.removeClass('hover-label')
    cy.on('mouseover', 'edge', onOver)
    cy.on('mouseout', 'edge', onOut)
    cy.on('mouseover', 'node', onNodeOver)
    cy.on('mouseout', 'node', onNodeOut)
    return () => {
      cy.off('mouseover', 'edge', onOver)
      cy.off('mouseout', 'edge', onOut)
      cy.off('mouseover', 'node', onNodeOver)
      cy.off('mouseout', 'node', onNodeOut)
    }
  }, [])

  // Selection choreography: path edges draw on sequentially seed→target, one
  // pass, then the target gets its ring. Zero duration under reduced motion
  // collapses every timeout to the same tick — effectively instant.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().removeClass('dimmed path-edge selected-target')
    if (!selectedPath || selectedPath.length < 2) return
    const parsed = parsePath(selectedPath)
    if (!parsed) return
    cy.elements().addClass('dimmed')
    const total = motionMs('--motion-trace')
    const hops = parsed.edgeTypes.length
    const timers: ReturnType<typeof setTimeout>[] = []
    for (let i = 0; i < hops; i++) {
      const source = parsed.nodes[i].key
      const target = parsed.nodes[i + 1].key
      const edgeType = parsed.edgeTypes[i]
      const edgeId = `${source}>${target}>${edgeType}`
      timers.push(
        setTimeout(
          () => {
            const edge = cy.getElementById(edgeId)
            edge.removeClass('dimmed').addClass('path-edge')
            edge.source().removeClass('dimmed')
            edge.target().removeClass('dimmed')
          },
          hops > 0 ? (total / hops) * i : 0,
        ),
      )
    }
    timers.push(
      setTimeout(() => {
        cy.getElementById(parsed.nodes[parsed.nodes.length - 1].key).addClass('selected-target')
      }, total),
    )
    return () => timers.forEach(clearTimeout)
  }, [selectedPath])

  const zoomBy = useCallback((factor: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
  }, [])
  const fit = useCallback(() => cyRef.current?.fit(undefined, 24), [])

  return (
    <div
      className="relative h-full min-h-[320px] w-full"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === '+' || e.key === '=') zoomBy(1.2)
        else if (e.key === '-') zoomBy(1 / 1.2)
        else if (e.key === '0') fit()
      }}
    >
      <div ref={containerRef} className="h-full w-full" />
      <div className="absolute right-2 top-2 flex gap-1">
        <button type="button" onClick={() => zoomBy(1.2)} aria-label="Zoom in" className="graph-control">
          +
        </button>
        <button type="button" onClick={() => zoomBy(1 / 1.2)} aria-label="Zoom out" className="graph-control">
          −
        </button>
        <button type="button" onClick={fit} aria-label="Fit graph" className="graph-control">
          fit
        </button>
        <button
          type="button"
          onClick={onToggleFullscreen}
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          className="graph-control"
        >
          {isFullscreen ? 'esc' : '⤢'}
        </button>
      </div>
    </div>
  )
}

export default function Constellation({
  recommendations,
  seedKey,
  platform,
  explainOn,
  selectedPath,
  onClearSelection,
}: {
  recommendations: Recommendation[]
  seedKey: string
  platform: string
  explainOn: boolean
  selectedPath: string[] | null
  onClearSelection: () => void
}) {
  const [expansions, setExpansions] = useState<Expansion[]>([])
  const [pendingExpand, setPendingExpand] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Reset accumulated expansions when the underlying response changes (a new
  // run, not a re-render) — recommendations is a fresh array each run.
  useEffect(() => {
    setExpansions([])
  }, [recommendations])

  const allSets = useMemo(
    () => [recommendations, ...expansions.map((e) => e.recommendations)],
    [recommendations, expansions],
  )
  const rawGraph = useMemo(
    () => buildGraph(seedKey, allSets, new Map(), {}),
    [seedKey, allSets],
  )
  const items = useItems(rawGraph.movieIds, platform)
  const tags = useTags()
  const itemTitles = useMemo(
    () => new Map((items.data ?? []).map((i) => [i.item_id, i.title])),
    [items.data],
  )
  const graph = useMemo(
    () => buildGraph(seedKey, allSets, itemTitles, tags.data ?? {}),
    [seedKey, allSets, itemTitles, tags.data],
  )

  const expand = useCallback(
    (nodeKey: string) => {
      if (pendingExpand || expansions.some((e) => e.seedKey === nodeKey)) return
      const itemId = Number(nodeKey.slice('item:'.length))
      setPendingExpand(nodeKey)
      similar({ seed_item_id: itemId, k: 8, explain: true }, platform)
        .then((response) => {
          const label = itemTitles.get(itemId)
          setExpansions((prev) => [
            ...prev,
            {
              seedKey: nodeKey,
              label: label ? tidyTitle(label).title : `#${itemId}`,
              recommendations: response.recommendations,
            },
          ])
        })
        .catch(() => undefined) // ponytail: expand is best-effort UI sugar, a failed fetch just no-ops
        .finally(() => setPendingExpand(null))
    },
    [pendingExpand, expansions, platform, itemTitles],
  )

  const removeExpansion = (seedKeyToRemove: string) =>
    setExpansions((prev) => prev.filter((e) => e.seedKey !== seedKeyToRemove))

  if (!explainOn || !graph.hasAnyPath) {
    return (
      <div className="flex h-full min-h-[320px] items-center justify-center text-center text-sm text-text-dim">
        Run with explain on to draw the constellation.
      </div>
    )
  }

  const breadcrumbs = expansions.length > 0 && (
    <div className="flex flex-wrap gap-1.5 px-1 pb-2">
      {expansions.map((e) => (
        <button
          key={e.seedKey}
          type="button"
          onClick={() => removeExpansion(e.seedKey)}
          className="rounded-full border border-hairline px-2 py-0.5 text-xs text-text-dim hover:border-text-faint hover:text-text"
        >
          {e.label} ✕
        </button>
      ))}
      {pendingExpand && <span className="text-xs text-text-faint">expanding…</span>}
    </div>
  )

  const canvas = (
    <GraphCanvas
      elements={graph.elements}
      seedKey={seedKey}
      selectedPath={selectedPath}
      onExpand={expand}
      onClearSelection={onClearSelection}
      isFullscreen={isFullscreen}
      onToggleFullscreen={() => setIsFullscreen((v) => !v)}
    />
  )

  return (
    <Dialog.Root open={isFullscreen} onOpenChange={setIsFullscreen}>
      {!isFullscreen && (
        <div className="flex h-full min-h-[320px] flex-col">
          {breadcrumbs}
          <div className="min-h-0 flex-1">{canvas}</div>
        </div>
      )}
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-void/80" />
        <Dialog.Content
          className="fixed inset-4 flex flex-col rounded-lg border border-hairline bg-surface p-4"
          onEscapeKeyDown={() => setIsFullscreen(false)}
        >
          <Dialog.Title className="sr-only">Constellation, fullscreen</Dialog.Title>
          {breadcrumbs}
          <div className="min-h-0 flex-1">{isFullscreen && canvas}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

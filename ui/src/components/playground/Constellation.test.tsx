import { describe, expect, it } from 'vitest'

import type { Recommendation } from '../../lib/types.ts'
import { buildGraph } from './Constellation.tsx'

const rec = (rank: number, itemId: number, path: string[]): Recommendation => ({
  item_id: itemId,
  rank,
  score: 1 / rank,
  sources: ['graph'],
  reason: null,
  path,
  metadata: {},
})

const hopOf = (graph: ReturnType<typeof buildGraph>, key: string): number =>
  graph.elements.find((e) => e.data.id === key)!.data.hop as number

describe('buildGraph hop rings', () => {
  it('places nodes at path distance from the primary roots', () => {
    const graph = buildGraph('item:1', [
      [rec(1, 3, ['item:1', 'HAS_TAG', 'tag:9', 'HAS_TAG', 'item:3'])],
    ])
    expect(hopOf(graph, 'item:1')).toBe(0)
    expect(hopOf(graph, 'tag:9')).toBe(1)
    expect(hopOf(graph, 'item:3')).toBe(2)
  })

  it('re-rings descendants when a later expansion shortcuts their parent', () => {
    // primary: 1 -> 2 -> 3 (item:3 at hop 2); expansion from item:3 adds
    // 3 -> 4; then a second expansion reveals a direct 1 -> 3 shortcut.
    // item:4 must land at hop 2 (one past its parent's new hop 1), not
    // stay frozen at hop 3 from the pre-shortcut pass.
    const graph = buildGraph('item:1', [
      [rec(1, 3, ['item:1', 'CO_RATED', 'item:2', 'CO_RATED', 'item:3'])],
      [rec(1, 4, ['item:3', 'CO_RATED', 'item:4'])],
      [rec(1, 3, ['item:1', 'CO_RATED', 'item:3'])],
    ])
    expect(hopOf(graph, 'item:3')).toBe(1)
    expect(hopOf(graph, 'item:4')).toBe(2)
  })
})

/** Graph explanation paths, verified against ingest/edges.py (node prefixes)
 *  and planes/graph/cte.py `_interleave` (alternating node/edge-type shape).
 *  A `Recommendation.path` looks like:
 *    ["item:2571", "CO_RATED", "item:79132"]
 *    ["item:1", "HAS_TAG", "tag:742", "HAS_TAG", "item:589"]
 *  i.e. node, edge-type, node, edge-type, node, ... — always odd length,
 *  always starting and ending on a node. */

export type NodeKind = 'movie' | 'user' | 'genre' | 'tag'

const KIND_BY_PREFIX: Record<string, NodeKind> = {
  item: 'movie',
  user: 'user',
  genre: 'genre',
  tag: 'tag',
}

export interface PathNode {
  kind: NodeKind
  /** the id/name after the prefix, e.g. "2571", "Comedy", "742" */
  id: string
  /** the full wire key, e.g. "item:2571" — stable identity for graph libs */
  key: string
}

export interface ParsedPath {
  nodes: PathNode[]
  /** edgeTypes[i] connects nodes[i] to nodes[i + 1]; length = nodes.length - 1 */
  edgeTypes: string[]
}

/** "item:2571" → {kind: 'movie', id: '2571', key: 'item:2571'}. null on any
 *  unrecognised prefix or missing id — callers decide whether to drop or warn. */
export function parseNodeKey(key: string): PathNode | null {
  const separator = key.indexOf(':')
  if (separator < 0) return null
  const prefix = key.slice(0, separator)
  const id = key.slice(separator + 1)
  const kind = KIND_BY_PREFIX[prefix]
  if (!kind || !id) return null
  return { kind, id, key }
}

/** Parses a full alternating path array. Returns null on anything malformed:
 *  empty, even length (missing a trailing node), or an unrecognised node key. */
export function parsePath(path: string[] | null | undefined): ParsedPath | null {
  if (!path || path.length === 0 || path.length % 2 === 0) return null
  const nodes: PathNode[] = []
  for (let i = 0; i < path.length; i += 2) {
    const node = parseNodeKey(path[i])
    if (!node) return null
    nodes.push(node)
  }
  const edgeTypes: string[] = []
  for (let i = 1; i < path.length; i += 2) {
    edgeTypes.push(path[i])
  }
  return { nodes, edgeTypes }
}

/** "HAS_TAG" → "has tag", "CO_RATED" → "co rated". */
export function humanizeEdgeType(edgeType: string): string {
  return edgeType.toLowerCase().replace(/_/g, ' ')
}

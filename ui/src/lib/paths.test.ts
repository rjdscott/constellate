import { describe, expect, it } from 'vitest'

import { humanizeEdgeType, parseNodeKey, parsePath } from './paths.ts'

describe('parseNodeKey', () => {
  it('parses all four node kinds', () => {
    expect(parseNodeKey('item:2571')).toEqual({ kind: 'movie', id: '2571', key: 'item:2571' })
    expect(parseNodeKey('user:5')).toEqual({ kind: 'user', id: '5', key: 'user:5' })
    expect(parseNodeKey('genre:Sci-Fi')).toEqual({ kind: 'genre', id: 'Sci-Fi', key: 'genre:Sci-Fi' })
    expect(parseNodeKey('tag:742')).toEqual({ kind: 'tag', id: '742', key: 'tag:742' })
  })

  it('rejects unknown prefixes and missing ids', () => {
    expect(parseNodeKey('movie:1')).toBeNull()
    expect(parseNodeKey('item:')).toBeNull()
    expect(parseNodeKey('no-colon')).toBeNull()
  })
})

describe('parsePath', () => {
  it('parses an alternating node/edge/node/... path', () => {
    const parsed = parsePath(['item:1', 'HAS_TAG', 'tag:742', 'HAS_TAG', 'item:589'])
    expect(parsed).not.toBeNull()
    expect(parsed?.nodes.map((n) => n.key)).toEqual(['item:1', 'tag:742', 'item:589'])
    expect(parsed?.edgeTypes).toEqual(['HAS_TAG', 'HAS_TAG'])
  })

  it('parses a single-hop path', () => {
    const parsed = parsePath(['item:2571', 'CO_RATED', 'item:79132'])
    expect(parsed?.nodes).toHaveLength(2)
    expect(parsed?.edgeTypes).toEqual(['CO_RATED'])
  })

  it('rejects malformed input', () => {
    expect(parsePath(null)).toBeNull()
    expect(parsePath(undefined)).toBeNull()
    expect(parsePath([])).toBeNull()
    // even length: missing the trailing node
    expect(parsePath(['item:1', 'HAS_TAG'])).toBeNull()
    // unrecognised node prefix anywhere in the chain
    expect(parsePath(['item:1', 'HAS_TAG', 'bogus:2'])).toBeNull()
  })
})

describe('humanizeEdgeType', () => {
  it('lowercases and de-underscores', () => {
    expect(humanizeEdgeType('HAS_TAG')).toBe('has tag')
    expect(humanizeEdgeType('RATED')).toBe('rated')
    expect(humanizeEdgeType('CO_RATED')).toBe('co rated')
  })
})

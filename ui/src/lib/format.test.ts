import { describe, expect, it } from 'vitest'

import { tidyTitle } from './format.ts'

describe('tidyTitle', () => {
  it('splits a trailing year', () => {
    expect(tidyTitle('Toy Story (1995)')).toEqual({ title: 'Toy Story', year: '1995' })
  })

  it('moves a catalog-sorted leading article back to the front', () => {
    expect(tidyTitle('Matrix, The (1999)')).toEqual({ title: 'The Matrix', year: '1999' })
  })

  it('handles titles with no year', () => {
    expect(tidyTitle('Amelie')).toEqual({ title: 'Amelie', year: null })
  })

  it('handles non-English articles', () => {
    expect(tidyTitle('Haine, La (1995)')).toEqual({ title: 'La Haine', year: '1995' })
  })
})

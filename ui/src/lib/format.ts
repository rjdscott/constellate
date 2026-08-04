/** Shared string sugar — house style lives in Overview.tsx, extracted so the
 *  playground/constellation views can share it. */

/** "(1999)" → dim suffix; "Matrix, The" → "The Matrix". MovieLens titles are
 *  catalog-sorted; people aren't. */
export function tidyTitle(raw: string): { title: string; year: string | null } {
  const year = /\((\d{4})\)\s*$/.exec(raw)
  let title = year ? raw.slice(0, year.index).trim() : raw
  const article = /^(.*), (The|A|An|Les|Le|La|L')$/.exec(title)
  if (article) title = `${article[2]} ${article[1]}`
  return { title, year: year ? year[1] : null }
}

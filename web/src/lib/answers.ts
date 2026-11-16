import type { Park, Puzzle } from './types'

// Words that don't help identify a park: "Rocky Mountain National Park" and
// "rocky mountain np" both reduce to "rocky mountain".
const FILLER = new Set(['national', 'park', 'parks', 'np', 'nat', 'preserve', 'and', 'state', 'the', 'of'])

/** 'Hawaiʻi Volcanoes National Park!' -> 'hawaii volcanoes' */
export function canonical(text: string): string {
  return text
    .normalize('NFKD') // split accented letters into letter + accent mark...
    .replace(/[̀-ͯ]/g, '') // ...then drop the accent marks
    .replace(/[ʻ'’‘`]/g, '') // ʻokina and apostrophes
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .split(' ')
    .filter((w) => w && !FILLER.has(w))
    .join(' ')
}

/** Edit distance: the fewest single-letter inserts, deletes or swaps to turn a into b. */
export function editDistance(a: string, b: string): number {
  // Classic dynamic programming, keeping only one row at a time.
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    const row = [i]
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      row[j] = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + cost)
    }
    prev = row
  }
  return prev[b.length]
}

/** Typos allowed: 1 for short names, 2 for longer ones. */
export function typoAllowance(target: string): number {
  return target.replace(/ /g, '').length <= 6 ? 1 : 2
}

function closest(guess: string, names: string[]): number {
  return Math.min(...names.map((n) => editDistance(guess, n)))
}

/**
 * Is a typed guess right?
 * 1. Exact match (after canonical()) to an accepted answer or the park's names.
 * 2. Otherwise a near miss within the typo allowance, but only if the guess is
 *    closer to this park than to every other park (so "glacier" isn't
 *    accepted for Glacier Bay, and "glacer bay" is).
 */
export function isCorrectGuess(guess: string, puzzle: Puzzle, park: Park, parks: Park[]): boolean {
  const g = canonical(guess)
  if (!g) return false

  const targets = [...new Set([...puzzle.accepted_answers, park.name, park.short_name].map(canonical))].filter(Boolean)
  if (targets.includes(g)) return true

  const nearMiss = targets.some((t) => editDistance(g, t) <= typoAllowance(t))
  if (!nearMiss) return false

  const others = parks.filter((p) => p.id !== park.id).flatMap((p) => [canonical(p.name), canonical(p.short_name)])
  return closest(g, targets) < closest(g, others)
}

/** 'Big Bend' -> 'B _ _   _ _ _ _': first letter, then one blank per letter. */
export function letterHint(shortName: string): string {
  return shortName
    .split(' ')
    .map((word, i) =>
      [...word]
        // The ʻokina counts as a letter to JavaScript but players don't type it.
        .map((c, j) => (/\p{L}/u.test(c) && c !== 'ʻ' && !(i === 0 && j === 0) ? '_' : c))
        .join(' '),
    )
    .join('   ')
}

/** A shuffle that comes out the same every time for the same seed (e.g. the date). */
export function seededShuffle<T>(items: T[], seed: string): T[] {
  let h = 1779033703 ^ seed.length
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 3432918353)
  const random = () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507)
    h = Math.imul(h ^ (h >>> 13), 3266489909)
    return ((h ^= h >>> 16) >>> 0) / 4294967296
  }
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

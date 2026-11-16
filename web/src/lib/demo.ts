import { newestPerSection } from './api'
import type { GameData, Park, ProfileSection, Puzzle } from './types'

// Dev-only demo mode: `npm run dev`, then open /?demo=2026-11-18.
// Loads local fixtures (pipeline/export_demo_fixtures.py) so the game and
// the reveal can be tried before a puzzle is live and before sections are
// approved. Draft sections are included here on purpose; they never reach
// the live site, because App only calls this when import.meta.env.DEV.

interface Fixtures {
  parks: Park[]
  puzzles: Puzzle[]
  profiles: ProfileSection[]
}

// import.meta.glob returns {} instead of failing if the file doesn't exist.
const fixtureFiles = import.meta.glob<Fixtures>('../demo/fixtures.json', { import: 'default' })

export async function loadDemoGame(date: string): Promise<GameData | null> {
  const load = Object.values(fixtureFiles)[0]
  if (!load) {
    throw new Error('Demo data missing: run `python pipeline/export_demo_fixtures.py` from the repo root.')
  }
  const { parks, puzzles, profiles } = await load()
  const puzzle = puzzles.find((p) => p.puzzle_date === date)
  if (!puzzle) return null
  const park = parks.find((p) => p.id === puzzle.park_id)!
  return { puzzle, park, parks, profile: newestPerSection(profiles.filter((s) => s.park_id === park.id)) }
}

import { supabase } from './supabase'
import type { GameData, Park, ProfileSection, Puzzle, SectionName } from './types'

// Columns are listed explicitly: the public key may only read some columns
// of parks and profile_sections, and select('*') would be refused.
const PUZZLE_COLUMNS =
  'id, puzzle_date, park_id, difficulty, answer_format, clue_1, clue_2, clue_3, wrong_answers, accepted_answers'
const PARK_COLUMNS = 'id, name, short_name, nps_code, states, photo'
const PROFILE_COLUMNS = 'id, park_id, section, body, sources, details, generated_at'

function client() {
  if (!supabase) {
    throw new Error('Supabase is not configured: copy web/.env.example to web/.env.local and fill it in.')
  }
  return supabase
}

/** The newest puzzle dated today or earlier (Row Level Security hides future ones anyway). */
export async function fetchTodaysPuzzle(today: string): Promise<Puzzle | null> {
  const { data, error } = await client()
    .from('puzzles')
    .select(PUZZLE_COLUMNS)
    .lte('puzzle_date', today)
    .order('puzzle_date', { ascending: false })
    .limit(1)
  if (error) throw error
  return (data?.[0] as Puzzle | undefined) ?? null
}

export async function fetchParks(): Promise<Park[]> {
  const { data, error } = await client().from('parks').select(PARK_COLUMNS).order('name')
  if (error) throw error
  return data as Park[]
}

/** The newest approved row for each section (only approved rows are readable). */
export async function fetchProfile(parkId: number): Promise<GameData['profile']> {
  const { data, error } = await client()
    .from('profile_sections')
    .select(PROFILE_COLUMNS)
    .eq('park_id', parkId)
    .order('generated_at', { ascending: false })
  if (error) throw error
  return newestPerSection(data as ProfileSection[])
}

export function newestPerSection(rows: ProfileSection[]): GameData['profile'] {
  const profile: GameData['profile'] = {}
  for (const row of rows) {
    // Rows arrive newest first, so keep the first one seen per section.
    profile[row.section as SectionName] ??= row
  }
  return profile
}

/** Everything for today's game, or null if no puzzle has been published yet. */
export async function loadGame(today: string): Promise<GameData | null> {
  const puzzle = await fetchTodaysPuzzle(today)
  if (!puzzle) return null
  const [parks, profile] = await Promise.all([fetchParks(), fetchProfile(puzzle.park_id)])
  const park = parks.find((p) => p.id === puzzle.park_id)
  if (!park) throw new Error(`Park ${puzzle.park_id} not found`)
  return { puzzle, park, parks, profile }
}

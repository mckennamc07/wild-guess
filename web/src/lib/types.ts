// The shapes of the rows the website reads from Supabase.
// They mirror the tables in supabase/migrations/, limited to the columns
// the public key is allowed to read.
//
// Key decision: string-literal unions (like AnswerFormat) mirror the
// Postgres enums, so TypeScript flags a typo or an unhandled format at
// build time.
//
// Why it matters: every component and lib file shares these shapes, so a
// database change shows up as a type error instead of a broken page.

export type AnswerFormat = 'type_in' | 'first_letter_count' | 'choice_confusable' | 'choice_easy'

export interface Puzzle {
  id: number
  puzzle_date: string // 'YYYY-MM-DD'
  park_id: number
  difficulty: 1 | 2 | 3 | 4
  answer_format: AnswerFormat
  clue_1: string
  clue_2: string
  clue_3: string
  wrong_answers: string[] // full park names; empty for typed formats
  accepted_answers: string[] // lowercase
}

export interface ParkPhoto {
  url: string
  title: string
  alt: string // description for screen readers
  caption: string
  credit: string // e.g. "NPS / Jacob W. Frank"
}

export interface Park {
  id: number
  name: string // "Acadia National Park"
  short_name: string // "Acadia"
  nps_code: string
  states: string[]
  photo: ParkPhoto | null // featured NPS photo, shown on the reveal
}

export type Confidence = 'strong' | 'limited' | 'thin'

export interface Source {
  title: string
  url: string
  quality?: 'high' | 'medium' | 'low'
}

// One piece of information about a nation, with its own citations.
export interface InfoField {
  text: string
  confidence: Confidence
  sources: Source[]
}

export interface Nation {
  name: string
  named_by: Source[] // the sources that connect this nation to the park
  little_information: boolean
  connection: InfoField | null
  present_day: InfoField | null
}

// profile_sections.details for people_history.
export interface PeopleDetails {
  confidence: Confidence
  player_note: string | null
  nations: Nation[]
  displacement: string
  documentation_note: string
}

export type SectionName = 'fun_facts' | 'formation' | 'people_history'

export interface ProfileSection {
  id: number
  park_id: number
  section: SectionName
  body: string // Markdown
  sources: Source[]
  details: PeopleDetails | null
  generated_at: string
}

// Everything one day's game needs.
export interface GameData {
  puzzle: Puzzle
  park: Park
  parks: Park[] // all parks, for the answer checker
  profile: Partial<Record<SectionName, ProfileSection>> // newest approved per section
}

import { describe, expect, it } from 'vitest'
import { canonical, editDistance, isCorrectGuess, letterHint, seededShuffle } from './answers'
import type { Park, Puzzle } from './types'

const park = (id: number, name: string, short_name: string): Park => ({
  id, name, short_name, nps_code: '', states: [], photo: null,
})

const PARKS = [
  park(1, 'Glacier National Park', 'Glacier'),
  park(2, 'Glacier Bay National Park & Preserve', 'Glacier Bay'),
  park(3, 'Yellowstone National Park', 'Yellowstone'),
  park(4, 'Hawaiʻi Volcanoes National Park', 'Hawaiʻi Volcanoes'),
  park(5, 'Zion National Park', 'Zion'),
  park(6, 'Great Smoky Mountains National Park', 'Great Smoky Mountains'),
]

const puzzleFor = (p: Park, accepted: string[]): Puzzle => ({
  id: 1, puzzle_date: '2026-11-16', park_id: p.id, difficulty: 4, answer_format: 'type_in',
  clue_1: '', clue_2: '', clue_3: '', wrong_answers: [], accepted_answers: accepted,
})

const guess = (text: string, p: Park, accepted: string[] = [p.short_name.toLowerCase()]) =>
  isCorrectGuess(text, puzzleFor(p, accepted), p, PARKS)

describe('canonical', () => {
  it('drops case, accents, the ʻokina, punctuation and filler words', () => {
    expect(canonical('Hawaiʻi Volcanoes National Park!')).toBe('hawaii volcanoes')
    expect(canonical('Glacier Bay National Park & Preserve')).toBe('glacier bay')
    expect(canonical('  zion np ')).toBe('zion')
  })
})

describe('editDistance', () => {
  it('counts single-letter changes', () => {
    expect(editDistance('yellowstone', 'yellowstone')).toBe(0)
    expect(editDistance('yelowstone', 'yellowstone')).toBe(1)
    expect(editDistance('zoin', 'zion')).toBe(2)
  })
})

describe('isCorrectGuess', () => {
  const [glacier, glacierBay, yellowstone, hawaii, zion, smokies] = PARKS

  it('accepts exact answers in any case or form', () => {
    expect(guess('YELLOWSTONE', yellowstone)).toBe(true)
    expect(guess('Yellowstone National Park', yellowstone)).toBe(true)
    expect(guess('yellowstone np', yellowstone)).toBe(true)
    expect(guess('Hawaii Volcanoes', hawaii)).toBe(true)
  })

  it('accepts small typos', () => {
    expect(guess('yelowstone', yellowstone)).toBe(true)
    expect(guess('hawaii volcanos', hawaii)).toBe(true)
    expect(guess('glacer bay', glacierBay)).toBe(true)
  })

  it('rejects a different, similar park', () => {
    expect(guess('glacier', glacierBay)).toBe(false)
    expect(guess('glacier bay', glacier)).toBe(false)
  })

  it('accepts nicknames from accepted_answers', () => {
    expect(guess('the smokies', smokies, ['great smoky mountains', 'smokies'])).toBe(true)
  })

  it('allows only one typo in short names', () => {
    expect(guess('zoin', zion)).toBe(false) // two letters swapped = 2 edits
    expect(guess('zio', zion)).toBe(true)
  })

  it('rejects empty and filler-only guesses', () => {
    expect(guess('', zion)).toBe(false)
    expect(guess('national park', zion)).toBe(false)
  })
})

describe('letterHint', () => {
  it('shows the first letter and a blank per letter', () => {
    expect(letterHint('Big Bend')).toBe('B _ _   _ _ _ _')
    expect(letterHint('Hawaiʻi Volcanoes')).toBe('H _ _ _ _ ʻ _   _ _ _ _ _ _ _ _ _')
  })
})

describe('seededShuffle', () => {
  it('is the same for the same seed and keeps every item', () => {
    const items = ['a', 'b', 'c', 'd']
    expect(seededShuffle(items, '2026-11-16')).toEqual(seededShuffle(items, '2026-11-16'))
    expect([...seededShuffle(items, '2026-11-16')].sort()).toEqual(items)
  })
})

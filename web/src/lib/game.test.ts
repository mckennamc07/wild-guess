// Tests for game.ts (run with `npm test`, using Vitest).
// Covers scoring (3/2/1/0), revealing a clue after each miss or skip, the
// game ending after a solve or three misses, and ignoring late guesses.
//
// Why it matters: these are the rules every player plays by.

import { describe, expect, it } from 'vitest'
import { NEW_GAME, applyGuess, cluesShown, isFinished, points } from './game'

describe('game rules', () => {
  it('starts on clue 1 with no points', () => {
    expect(cluesShown(NEW_GAME)).toBe(1)
    expect(isFinished(NEW_GAME)).toBe(false)
    expect(points(NEW_GAME)).toBe(0)
  })

  it('solving on clue 1 scores 3 and ends the game', () => {
    const s = applyGuess(NEW_GAME, 'zion', true)
    expect(s.solvedOn).toBe(1)
    expect(points(s)).toBe(3)
    expect(isFinished(s)).toBe(true)
  })

  it('each wrong guess or skip reveals the next clue', () => {
    let s = applyGuess(NEW_GAME, 'arches', false)
    expect(cluesShown(s)).toBe(2)
    s = applyGuess(s, '', false) // skip
    expect(cluesShown(s)).toBe(3)
    s = applyGuess(s, 'zion', true)
    expect(points(s)).toBe(1)
  })

  it('three misses ends the game with 0 points', () => {
    let s = NEW_GAME
    for (const g of ['a', 'b', 'c']) s = applyGuess(s, g, false)
    expect(isFinished(s)).toBe(true)
    expect(points(s)).toBe(0)
    expect(cluesShown(s)).toBe(3)
  })

  it('ignores guesses after the game ends', () => {
    const solved = applyGuess(NEW_GAME, 'zion', true)
    expect(applyGuess(solved, 'more', false)).toBe(solved)
  })
})

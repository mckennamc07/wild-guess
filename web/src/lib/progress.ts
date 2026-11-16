import { NEW_GAME, type GameState } from './game'

// Today's game is saved in the browser so a refresh doesn't wipe it.
// localStorage can be blocked (private windows, strict settings), so every
// access is wrapped: if it fails, the game still works, it just won't persist.

const key = (date: string) => `wild-guess:game:${date}`

export function loadProgress(date: string): GameState {
  try {
    const saved = localStorage.getItem(key(date))
    return saved ? (JSON.parse(saved) as GameState) : NEW_GAME
  } catch {
    return NEW_GAME
  }
}

export function saveProgress(date: string, state: GameState): void {
  try {
    localStorage.setItem(key(date), JSON.stringify(state))
  } catch {
    // Storage unavailable: nothing to do.
  }
}

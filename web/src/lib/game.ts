// The game rules, kept free of React so they're easy to test.
// The whole game state is just the list of guesses and when (if) it was solved;
// everything else is worked out from those two.
//
// Key decisions: storing the fewest facts possible (and deriving clues shown,
// points and "finished") means the saved state can't contradict itself;
// applyGuess returns a new object instead of changing the old one, which is
// how React expects state to be updated.
//
// Why it matters: these are the scoring and clue-unlock rules every player
// plays by, tested in game.test.ts.

export interface GameState {
  guesses: string[] // in order; '' means "skipped to the next clue"
  solvedOn: 1 | 2 | 3 | null // which clue the right answer came on
}

export const NEW_GAME: GameState = { guesses: [], solvedOn: null }

export function isFinished(s: GameState): boolean {
  return s.solvedOn !== null || s.guesses.length >= 3
}

/** How many clues to show: one more after each wrong guess, up to 3. */
export function cluesShown(s: GameState): 1 | 2 | 3 {
  return (s.solvedOn ?? Math.min(s.guesses.length + 1, 3)) as 1 | 2 | 3
}

/** 3 points on clue 1, 2 on clue 2, 1 on clue 3, 0 if not solved. */
export function points(s: GameState): number {
  return s.solvedOn ? 4 - s.solvedOn : 0
}

/** Record a guess (or a skip, as ''), returning the new state. */
export function applyGuess(s: GameState, guess: string, correct: boolean): GameState {
  if (isFinished(s)) return s
  const guesses = [...s.guesses, guess]
  return { guesses, solvedOn: correct ? (guesses.length as 1 | 2 | 3) : null }
}

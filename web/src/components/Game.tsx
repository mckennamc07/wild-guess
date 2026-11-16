import { useEffect, useState } from 'react'
import { applyGuess, cluesShown, isFinished } from '../lib/game'
import { formatPuzzleDate } from '../lib/dates'
import { loadProgress, saveProgress } from '../lib/progress'
import type { AnswerFormat, GameData } from '../lib/types'
import { GuessInput } from './GuessInput'
import { Reveal } from './Reveal'

const FORMAT_LABELS: Record<AnswerFormat, string> = {
  type_in: 'Type the park’s name',
  first_letter_count: 'Fill in the park’s name',
  choice_confusable: 'Pick the park',
  choice_easy: 'Pick the park',
}

interface Props {
  data: GameData
  date: string
  storagePrefix: string // keeps demo games separate from real ones
}

export function Game({ data, date, storagePrefix }: Props) {
  const storageKey = storagePrefix + date
  // The function form runs only once, on the first render.
  const [state, setState] = useState(() => loadProgress(storageKey))

  // Whenever the state changes, save it.
  useEffect(() => saveProgress(storageKey, state), [storageKey, state])

  const { puzzle } = data
  const shown = cluesShown(state)

  if (isFinished(state)) {
    return <Reveal data={data} state={state} />
  }

  const wrongGuesses = state.guesses.filter(Boolean)

  return (
    <section className="game" aria-live="polite">
      <p className="puzzle-meta">
        {formatPuzzleDate(date)} · {FORMAT_LABELS[puzzle.answer_format]}
      </p>

      {/* All three boxes are always on screen. A locked clue shows only its
          label; its text isn't put on the page until it unlocks, so it can't
          be read with the browser's inspect tool either. */}
      <ol className="clues">
        {[puzzle.clue_1, puzzle.clue_2, puzzle.clue_3].map((clue, i) => {
          const unlocked = i < shown
          return (
            <li key={i} className={unlocked ? 'clue' : 'clue locked'}>
              <span className="clue-label">
                Clue {i + 1}
                {!unlocked && <span className="visually-hidden"> (locked)</span>}
              </span>
              {unlocked && <p className="clue-text">{clue}</p>}
            </li>
          )
        })}
      </ol>

      {wrongGuesses.length > 0 && (
        <p className="wrong-guesses">
          Not it: {wrongGuesses.map((g, i) => <span key={i} className="chip">{g}</span>)}
        </p>
      )}

      <GuessInput
        data={data}
        guesses={state.guesses}
        cluesShown={shown}
        onGuess={(guess, correct) => setState((s) => applyGuess(s, guess, correct))}
      />
    </section>
  )
}

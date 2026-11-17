// How the player answers. The puzzle's answer format picks the control:
// a text box (type_in, first_letter_count, with a letter hint for the
// latter) or four multiple-choice buttons (choice_confusable, choice_easy).
//
// Key decisions:
// - Typed guesses use the fuzzy checker in lib/answers.ts, so small typos and
//   "national park" are forgiven.
// - Choices are shuffled with a seed (the puzzle date), so the order is the
//   same for everyone and doesn't change on refresh. useMemo avoids
//   reshuffling on every render.
// - A skip is recorded as an empty guess, so skipping and guessing wrong
//   both reveal the next clue the same way.
//
// Why it matters: difficulty in Wild Guess comes from the answer format,
// and this is where the four formats become different experiences.

import { useMemo, useState, type FormEvent } from 'react'
import { isCorrectGuess, letterHint, seededShuffle } from '../lib/answers'
import type { GameData } from '../lib/types'

interface Props {
  data: GameData
  guesses: string[]
  cluesShown: number
  onGuess: (guess: string, correct: boolean) => void
}

export function GuessInput({ data, guesses, cluesShown, onGuess }: Props) {
  const { puzzle, park, parks } = data
  const isChoice = puzzle.answer_format.startsWith('choice')
  const skipLabel = cluesShown < 3 ? 'Next clue' : 'Show the answer'

  if (isChoice) {
    return <Choices data={data} guesses={guesses} onGuess={onGuess} skipLabel={skipLabel} />
  }

  return (
    <TypedGuess
      hint={puzzle.answer_format === 'first_letter_count' ? letterHint(park.short_name) : null}
      onSubmit={(text) => onGuess(text.trim(), isCorrectGuess(text, puzzle, park, parks))}
      onSkip={() => onGuess('', false)}
      skipLabel={skipLabel}
    />
  )
}

function TypedGuess(props: {
  hint: string | null
  onSubmit: (text: string) => void
  onSkip: () => void
  skipLabel: string
}) {
  const [text, setText] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault() // stop the browser reloading the page on form submit
    if (!text.trim()) return
    props.onSubmit(text)
    setText('')
  }

  return (
    <form className="guess" onSubmit={submit}>
      {props.hint && (
        <p className="letter-hint" aria-label="Letter hint">
          <span className="letters">{props.hint}</span> National Park
        </p>
      )}
      <label htmlFor="guess-input" className="visually-hidden">Your guess</label>
      <input
        id="guess-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Name the park"
        autoComplete="off"
        autoCapitalize="words"
        autoFocus
      />
      <div className="actions">
        <button type="submit" className="primary">Guess</button>
        <button type="button" className="secondary" onClick={props.onSkip}>{props.skipLabel}</button>
      </div>
    </form>
  )
}

function Choices(props: {
  data: GameData
  guesses: string[]
  onGuess: (guess: string, correct: boolean) => void
  skipLabel: string
}) {
  const { puzzle, park } = props.data
  // Same order every time for the same day, so a refresh doesn't reshuffle.
  const options = useMemo(
    () => seededShuffle([...puzzle.wrong_answers, park.name], puzzle.puzzle_date),
    [puzzle, park],
  )

  return (
    <div className="guess">
      <div className="choices">
        {options.map((option) => (
          <button
            key={option}
            className="choice"
            disabled={props.guesses.includes(option)}
            onClick={() => props.onGuess(option, option === park.name)}
          >
            {option}
          </button>
        ))}
      </div>
      <div className="actions">
        <button className="secondary" onClick={() => props.onGuess('', false)}>{props.skipLabel}</button>
      </div>
    </div>
  )
}

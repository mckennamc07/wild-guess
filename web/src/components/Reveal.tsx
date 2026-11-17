// The after-game screen: the result, the park's name and photo, all three
// clues (marking ones you didn't need), and tabs for Fun fact, How it
// formed, and Who lived here first.
//
// Key decisions:
// - Tabs use the ARIA tab roles (tablist, tab, tabpanel), so keyboard and
//   screen-reader users can tell which section is open.
// - Section text is Markdown rendered with react-markdown, which doesn't run
//   raw HTML, so stored text can't inject markup into the page.
// - A section with no approved row shows "coming soon" instead of anything
//   unreviewed.
//
// Why it matters: this is where players learn about the park, the second
// half of what Wild Guess is for.

import { useState } from 'react'
import Markdown from 'react-markdown'
import type { GameState } from '../lib/game'
import type { GameData, SectionName } from '../lib/types'
import { PeopleHistory } from './PeopleHistory'
import { Sources } from './Sources'

const TABS: { id: SectionName; label: string }[] = [
  { id: 'fun_facts', label: 'Fun fact' },
  { id: 'formation', label: 'How it formed' },
  { id: 'people_history', label: 'Who lived here first' },
]

export function Reveal({ data, state }: { data: GameData; state: GameState }) {
  const [tab, setTab] = useState<SectionName>('fun_facts')
  const { puzzle, park, profile } = data
  const clues = [puzzle.clue_1, puzzle.clue_2, puzzle.clue_3]
  const solved = state.solvedOn !== null

  return (
    <section className="reveal">
      <div className={`result ${solved ? 'solved' : 'missed'}`}>
        <p className="result-line">
          {solved
            ? `You got it on clue ${state.solvedOn}!`
            : 'Not this time. The park was…'}
        </p>
        <h2 className="park-name">{park.name}</h2>
        <p className="park-states">{park.states.join(' · ')}</p>
      </div>

      {/* Outside the result block so it can stretch past the text column. */}
      {park.photo && (
        <figure className="park-photo">
          <img src={park.photo.url} alt={park.photo.alt} loading="lazy" />
          <figcaption>
            {park.photo.title}
            {park.photo.credit && <span className="credit"> · {park.photo.credit}</span>}
          </figcaption>
        </figure>
      )}

      <details className="all-clues" open={!solved}>
        <summary>The clues</summary>
        <ol className="clues">
          {clues.map((clue, i) => (
            <li key={i} className="clue">
              <span className="clue-label">
                Clue {i + 1}
                {solved && i + 1 > state.solvedOn! && <em> · a clue you didn’t need</em>}
              </span>
              <p>{clue}</p>
            </li>
          ))}
        </ol>
      </details>

      <div className="tabs" role="tablist" aria-label="About this park">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            className={tab === t.id ? 'tab active' : 'tab'}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'people_history' ? (
          <>
            {profile.people_history?.details ? (
              <PeopleHistory details={profile.people_history.details} sources={profile.people_history.sources} />
            ) : (
              <ComingSoon />
            )}
            <p className="native-land">
              Explore the Indigenous territories of this region on{' '}
              <a href="https://native-land.ca" target="_blank" rel="noreferrer">Native Land</a>. Territory maps
              are approximate.
            </p>
          </>
        ) : profile[tab] ? (
          <>
            <div className="section-body">
              <Markdown>{profile[tab]!.body}</Markdown>
            </div>
            <Sources sources={profile[tab]!.sources} />
          </>
        ) : (
          <ComingSoon />
        )}
      </div>
    </section>
  )
}

function ComingSoon() {
  return <p className="coming-soon">In-depth, sourced research for this section is coming soon.</p>
}

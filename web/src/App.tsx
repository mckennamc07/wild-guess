import { useEffect, useState } from 'react'
import { Game } from './components/Game'
import { HowItWorks } from './components/HowItWorks'
import { loadGame } from './lib/api'
import { easternToday } from './lib/dates'
import { clearProgress } from './lib/progress'
import type { GameData } from './lib/types'

// What the page is showing. A "union type": exactly one of these at a time,
// and TypeScript makes sure we handle each one.
type Status =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | { kind: 'ready'; data: GameData; date: string; demo: boolean }

// Demo mode exists only in development (`npm run dev`). In the production
// build import.meta.env.DEV is false, so this is null and the demo code and
// its draft data are left out of the site entirely.
const demoDate = import.meta.env.DEV ? new URLSearchParams(window.location.search).get('demo') : null

export default function App() {
  const [status, setStatus] = useState<Status>({ kind: 'loading' })

  // Runs once after the first render: fetch today's game.
  useEffect(() => {
    async function load() {
      try {
        const date = demoDate ?? easternToday()
        const data = demoDate
          ? await (await import('./lib/demo')).loadDemoGame(date)
          : await loadGame(date)
        setStatus(data ? { kind: 'ready', data, date: data.puzzle.puzzle_date, demo: !!demoDate } : { kind: 'empty' })
      } catch (e) {
        setStatus({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
      }
    }
    load()
  }, [])

  return (
    <div className="page">
      <header className="site-header">
        <h1>Wild Guess</h1>
        <p className="tagline">Three clues. One national park.</p>
      </header>

      <main>
        {status.kind === 'loading' && <p className="status">Loading today's park…</p>}
        {status.kind === 'error' && (
          <p className="status error">Something went wrong loading the puzzle. {status.message}</p>
        )}
        {status.kind === 'empty' && (
          <p className="status">The first puzzle arrives Monday. Check back then!</p>
        )}
        {status.kind === 'ready' && (
          <>
            {/* import.meta.env.DEV is replaced with `false` in the production build,
                so the bundler deletes this whole block from the live site. */}
            {import.meta.env.DEV && status.demo && (
              <p className="demo-banner">
                Demo mode: local draft data, not the live site.{' '}
                <button
                  className="link-button"
                  onClick={() => {
                    clearProgress(`demo:${status.date}`)
                    window.location.reload()
                  }}
                >
                  Reset this puzzle
                </button>
              </p>
            )}
            <Game data={status.data} date={status.date} storagePrefix={status.demo ? 'demo:' : ''} />
          </>
        )}
      </main>

      <HowItWorks />
    </div>
  )
}

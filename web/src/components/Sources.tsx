// A collapsible list of source links for a profile section, plus the
// "Researched with Exa" credit.
//
// Key decisions: links open in a new tab with rel="noreferrer" (the
// opened page can't control this one), and an empty list renders nothing.
//
// Why it matters: every profile claim comes from a source, and showing
// them lets players check it themselves.

import type { Source } from '../lib/types'

export function Sources({ sources, label = 'Sources' }: { sources: Source[]; label?: string }) {
  if (sources.length === 0) return null
  return (
    <details className="sources">
      <summary>
        {label} ({sources.length})
      </summary>
      <ul>
        {sources.map((s) => (
          <li key={s.url}>
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.title}
            </a>
          </li>
        ))}
      </ul>
      <p className="exa-credit">
        Researched with{' '}
        <a href="https://exa.ai" target="_blank" rel="noreferrer">
          Exa
        </a>
      </p>
    </details>
  )
}

import Markdown from 'react-markdown'
import type { Nation, PeopleDetails, Source } from '../lib/types'
import { Sources } from './Sources'

export function PeopleHistory({ details, sources }: { details: PeopleDetails; sources: Source[] }) {
  return (
    <div className="people">
      {details.player_note && (
        <div className="player-note">
          <Markdown>{details.player_note}</Markdown>
        </div>
      )}

      {details.nations.length > 0 ? (
        <>
          <p className="people-intro">Nations with ties to this land. Tap one to read more.</p>
          <ul className="nations">
            {details.nations.map((n) => (
              <li key={n.name}>
                <NationEntry nation={n} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="coming-soon">Little is documented in the sources found.</p>
      )}

      {details.displacement && (
        <div className="displacement">
          <h3>Displacement when the park was created</h3>
          <Markdown>{details.displacement}</Markdown>
        </div>
      )}

      {details.documentation_note && <p className="doc-note">{details.documentation_note}</p>}

      <Sources sources={sources} label="All sources for this section" />
    </div>
  )
}

function NationEntry({ nation }: { nation: Nation }) {
  const limited = [nation.connection, nation.present_day].some((f) => f && f.confidence !== 'strong')
  // Every source behind this nation, without repeats.
  const sources = [
    ...new Map(
      [...nation.named_by, ...(nation.connection?.sources ?? []), ...(nation.present_day?.sources ?? [])].map(
        (s) => [s.url, s],
      ),
    ).values(),
  ]

  return (
    <details className="nation">
      <summary>{nation.name}</summary>
      <div className="nation-body">
        {nation.little_information && (
          <p className="note">Little information was found about this nation’s ties to the park.</p>
        )}
        {nation.connection && <Markdown>{nation.connection.text}</Markdown>}
        {nation.present_day && (
          <div className="today">
            <strong>Today: </strong>
            <Markdown>{nation.present_day.text}</Markdown>
          </div>
        )}
        {limited && <p className="note">Based on limited sources.</p>}
        <Sources sources={sources} />
      </div>
    </details>
  )
}

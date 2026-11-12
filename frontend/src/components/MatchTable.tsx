import { Link, useNavigate } from 'react-router'
import type { MatchSummary } from '../api/client'
import { duration } from '../format'

export function Sides({ sides }: { sides?: string | null }) {
  if (!sides || sides === 'unknown') return <span className="muted">–</span>
  return <span className={`side ${sides === 'ct' ? 'ct' : sides === 't' ? 't' : ''}`}>{sides}</span>
}

export function MatchTitle({ m }: { m: MatchSummary }) {
  return (
    <span className="teams">
      {m.team1 ?? '?'}
      <span className="vs">vs</span>
      {m.team2 ?? '?'}
    </span>
  )
}

/** Match list; a row opens the match page. */
export default function MatchTable({ items, extra }: { items: MatchSummary[]; extra?: (m: MatchSummary) => React.ReactNode }) {
  const navigate = useNavigate()
  if (!items.length) return <p className="empty">No match.</p>
  return (
    <div className="table-wrap">
      <table className="results">
        <thead>
          <tr>
            <th>Release</th>
            <th>Year</th>
            <th>Map</th>
            <th>Match</th>
            <th className="hide-sm">POV</th>
            <th className="hide-sm">Side</th>
            <th className="hide-sm">Server</th>
            <th className="num hide-sm">Length</th>
            {extra && <th className="num">This player</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.id} className="row" onClick={() => navigate(`/match/${m.id}`)}>
              <td className="mono">{m.release}</td>
              <td title={m.year_basis ?? ''}>
                {m.year}
                {m.file_date && <div className="sub nowrap">{m.file_date}</div>}
              </td>
              <td>{m.map}</td>
              <td>
                <Link to={`/match/${m.id}`} onClick={(e) => e.stopPropagation()}>
                  <MatchTitle m={m} />
                </Link>
                {m.scores && <div className="sub">{m.scores}</div>}
              </td>
              <td className="hide-sm">{m.pov === 'HLTV' ? <span className="hltv">HLTV</span> : m.pov}</td>
              <td className="hide-sm">
                <Sides sides={m.sides} />
              </td>
              <td className="hide-sm sub">{m.servers.join(' | ')}</td>
              <td className="num hide-sm">{duration(m.duration_s)}</td>
              {extra && <td className="num">{extra(m)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

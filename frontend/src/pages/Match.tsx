import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { api, type Lineup } from '../api/client'
import { MatchTitle, Sides } from '../components/MatchTable'
import PlayButton from '../components/PlayButton'
import RoundsGrid from '../components/RoundsGrid'
import { duration } from '../format'

function LineupTable({ lineup, title }: { lineup: Lineup; title: string }) {
  return (
    <div className="lineup">
      <h3>{title}</h3>
      <table>
        <thead>
          <tr>
            <th>Player</th>
            <th className="num">K</th>
            <th className="num">D</th>
            <th className="num">HS</th>
          </tr>
        </thead>
        <tbody>
          {lineup.players.map((p) => (
            <tr key={p.name_id}>
              <td>
                <Link to={`/player/${p.name_id}`}>{p.name}</Link>
                {p.aliases.length > 0 && <div className="sub">also: {p.aliases.join(', ')}</div>}
                {p.steamid && <div className="sid">{p.steamid}</div>}
              </td>
              <td className="num">{p.kills}</td>
              <td className="num">{p.deaths}</td>
              <td className="num">{p.headshots}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Match() {
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['match', id], queryFn: () => api.match(id), enabled: Number.isFinite(id) })
  if (q.isPending) return <p className="muted">Loading…</p>
  if (q.isError) return <p role="alert" className="error">Match not found.</p>
  const { summary: m, lineups, demos, sources } = q.data
  const main = lineups.filter((l) => l.key === 'team1' || l.key === 'team2')
  const others = lineups.filter((l) => l.key !== 'team1' && l.key !== 'team2')
  return (
    <article className="match">
      <p className="crumbs">
        <Link to="/">Library</Link> › {m.release} · {m.year}
      </p>
      <h1>
        <MatchTitle m={m} /> <span className="muted">· {m.map}</span>
      </h1>
      <p className="meta-line">
        {m.pov === 'HLTV' ? <span className="hltv">HLTV</span> : <>POV {m.pov}</>} · side <Sides sides={m.sides} /> · {duration(m.duration_s)} ·{' '}
        {m.kills} kills{m.scores && <> · <span className="hud">{m.scores}</span></>}
      </p>
      <section className="lineups">
        {main.map((l) => (
          <LineupTable key={l.key} lineup={l} title={l.tag ?? (l.key === 'team1' ? 'Team 1' : 'Team 2')} />
        ))}
      </section>
      {demos.map((d) => (
        <section key={d.sha1} className="rounds">
          <h2>
            <PlayButton demo={d} title={d.engine ? `Play from the start with ${d.engine}` : undefined}>
              ▶ Play
            </PlayButton>{' '}
            Rounds · <span className="mono">{d.label}</span>{' '}
            <span className="sub">
              {d.recorder_kind === 'hltv' ? 'HLTV' : `POV ${d.recorder_name ?? '?'}`} · protocol {d.net_protocol} · {d.engine ?? 'no install'} · {duration(Math.round(d.duration_s ?? 0))} · {d.rounds}{' '}
              rounds
            </span>
          </h2>
          <RoundsGrid demo={d} />
        </section>
      ))}
      {demos.some((d) => !d.engine) && (
        <p className="note">
          {demos.find((d) => !d.engine)?.play_problem} — see <Link to="/settings">Settings</Link>.
        </p>
      )}
      <p className="note">▶ R starts 1 s before the round, a kill time 5 s before the kill: the game fast-forwards without sound, then plays normally.</p>
      {others.length > 0 && (
        <details>
          <summary>Other names seen on the server ({others.reduce((n, l) => n + l.players.length, 0)})</summary>
          <section className="lineups">
            {others.map((l) => (
              <LineupTable key={l.key} lineup={l} title={l.tag ?? l.key} />
            ))}
          </section>
        </details>
      )}
      <dl className="facts">
        <dt>Release</dt>
        <dd>
          {m.release} <span className="sub">— {q.data.release_basis.join('; ')}</span>
        </dd>
        <dt>Year</dt>
        <dd>
          {m.year} <span className="sub">— {m.year_basis}</span>
        </dd>
        <dt>Teams</dt>
        <dd>{q.data.team_basis}</dd>
        <dt>Server</dt>
        <dd>{m.servers.join(' | ') || '–'}</dd>
        <dt>Library name</dt>
        <dd className="mono">{q.data.library_name}</dd>
        <dt>Found in</dt>
        <dd className="mono">
          {sources.map((s, i) => (
            <div key={i}>
              {s.source_path} <span className="sub">› {s.member}</span>
            </div>
          ))}
        </dd>
      </dl>
    </article>
  )
}

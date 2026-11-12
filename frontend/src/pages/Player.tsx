import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { api, type PlayerSummary } from '../api/client'
import MatchTable from '../components/MatchTable'

function NameList({ title, items }: { title: string; items: PlayerSummary[] }) {
  if (!items.length) return null
  return (
    <p>
      <span className="muted">{title}: </span>
      {items.map((p, i) => (
        <span key={p.name_id}>
          {i > 0 && ', '}
          <Link to={`/player/${p.name_id}`}>{p.name}</Link>
          {p.steamid && <span className="sid"> {p.steamid}</span>} <span className="sub">({p.matches})</span>
        </span>
      ))}
    </p>
  )
}

export default function Player() {
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['player', id], queryFn: () => api.player(id), enabled: Number.isFinite(id) })
  if (q.isPending) return <p className="muted">Loading…</p>
  if (q.isError) return <p role="alert" className="error">Player name not found.</p>
  const { player: p, matches, headshots } = q.data
  const perMatch = new Map(matches.map((x) => [x.match.id, x]))
  return (
    <article>
      <p className="crumbs">
        <Link to="/players">Players</Link>
      </p>
      <h1>{p.name}</h1>
      {p.steamid && <p className="sid">{p.steamid}</p>}
      <div className="stats">
        <div>
          <b>{p.matches}</b>
          <span>matches</span>
        </div>
        <div>
          <b>{p.kills}</b>
          <span>kills</span>
        </div>
        <div>
          <b>{p.deaths}</b>
          <span>deaths</span>
        </div>
        <div>
          <b>{headshots}</b>
          <span>headshots</span>
        </div>
      </div>
      <NameList title="Other names with the same SteamID" items={q.data.same_steamid} />
      <NameList title="Same name, other or no SteamID (maybe someone else)" items={q.data.same_name} />
      <h2>Matches</h2>
      <MatchTable
        items={matches.map((x) => x.match)}
        extra={(m) => {
          const x = perMatch.get(m.id)
          return x ? `${x.kills} / ${x.deaths}` : ''
        }}
      />
    </article>
  )
}

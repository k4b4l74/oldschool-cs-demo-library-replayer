import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { api } from '../api/client'
import MatchTable from '../components/MatchTable'

export default function Team() {
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['team', id], queryFn: () => api.team(id), enabled: Number.isFinite(id) })
  if (q.isPending) return <p className="muted">Loading…</p>
  if (q.isError) return <p role="alert" className="error">Team not found.</p>
  const { team, players, matches } = q.data
  return (
    <article>
      <p className="crumbs">
        <Link to="/teams">Teams</Link>
      </p>
      <h1>{team.tag}</h1>
      <p className="muted">{team.matches} matches</p>
      <h2>Players seen in its line-ups</h2>
      <ul className="chips">
        {players.map((p) => (
          <li key={p.name_id}>
            <Link className="chip" to={`/player/${p.name_id}`}>
              {p.name} <b>{p.matches}</b>
            </Link>
          </li>
        ))}
      </ul>
      <h2>Matches</h2>
      <MatchTable items={matches} />
    </article>
  )
}

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { api } from '../api/client'
import SearchInput from '../components/SearchInput'

export default function Players() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const list = useQuery({ queryKey: ['players', q], queryFn: () => api.players(q), placeholderData: keepPreviousData })
  return (
    <>
      <h1>Players</h1>
      <p className="muted">
        Names exactly as printed in the demos. The same name with another SteamID, or with none, is listed apart: it may not be the same person.
      </p>
      <SearchInput label="Search players" placeholder="name or SteamID" value={q} onChange={(v) => setParams(v ? { q: v } : {}, { replace: true })} />
      {list.data && (
        <table className="results compact">
          <thead>
            <tr>
              <th>Name</th>
              <th>SteamID</th>
              <th className="num">Matches</th>
              <th className="num">K</th>
              <th className="num">D</th>
            </tr>
          </thead>
          <tbody>
            {list.data.map((p) => (
              <tr key={p.name_id}>
                <td>
                  <Link to={`/player/${p.name_id}`}>{p.name}</Link>
                </td>
                <td className="sid">{p.steamid || '–'}</td>
                <td className="num">{p.matches}</td>
                <td className="num">{p.kills}</td>
                <td className="num">{p.deaths}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {list.data?.length === 0 && <p className="empty">No player name matches.</p>}
    </>
  )
}

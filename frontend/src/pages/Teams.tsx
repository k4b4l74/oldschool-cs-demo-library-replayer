import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router'
import { api } from '../api/client'
import SearchInput from '../components/SearchInput'

export default function Teams() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const list = useQuery({ queryKey: ['teams', q], queryFn: () => api.teams(q), placeholderData: keepPreviousData })
  return (
    <>
      <h1>Teams</h1>
      <p className="muted">Clan tags as printed in the demos. Similar tags are not merged: a tag can be shared by different clans.</p>
      <SearchInput label="Search teams" placeholder="tag" value={q} onChange={(v) => setParams(v ? { q: v } : {}, { replace: true })} />
      {list.data && (
        <ul className="chips">
          {list.data.map((t) => (
            <li key={t.id}>
              <Link className="chip" to={`/team/${t.id}`}>
                {t.tag} <b>{t.matches}</b>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {list.data?.length === 0 && <p className="empty">No team tag matches.</p>}
    </>
  )
}

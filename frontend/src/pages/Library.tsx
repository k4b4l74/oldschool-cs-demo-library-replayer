import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { api, type MatchQuery } from '../api/client'
import MatchTable from '../components/MatchTable'
import Pager from '../components/Pager'
import SearchInput from '../components/SearchInput'

const SIZE = 50
const TEXT = ['q', 'player', 'team', 'steamid'] as const

/** Filters live in the URL, so a search can be bookmarked or shared. */
function useFilters() {
  const [params, setParams] = useSearchParams()
  const query: MatchQuery = {
    q: params.get('q') ?? '',
    player: params.get('player') ?? '',
    team: params.get('team') ?? '',
    steamid: params.get('steamid') ?? '',
    map: params.get('map') ?? '',
    release: params.getAll('release'),
    year_from: params.get('year_from') ?? '',
    year_to: params.get('year_to') ?? '',
    pov: (params.get('pov') ?? '') as MatchQuery['pov'],
    sort: params.get('sort') ?? 'date',
    dir: (params.get('dir') ?? 'asc') as MatchQuery['dir'],
    page: Number(params.get('page') ?? 1) || 1,
    size: SIZE,
  }
  const update = (changes: Record<string, string | string[] | number | undefined>, keepPage = false) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(changes)) {
      next.delete(k)
      for (const one of Array.isArray(v) ? v : v === undefined || v === '' ? [] : [String(v)]) next.append(k, one)
    }
    if (!keepPage) next.delete('page')
    setParams(next, { replace: true })
  }
  return { query, update, reset: () => setParams(new URLSearchParams(), { replace: true }) }
}

function SearchBox({ label, value, placeholder, onChange }: { label: string; value: string; placeholder?: string; onChange: (v: string) => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      <SearchInput label={label} className="" value={value} placeholder={placeholder} onChange={onChange} />
    </label>
  )
}

export default function Library() {
  const { query, update, reset } = useFilters()
  const stats = useQuery({ queryKey: ['stats'], queryFn: api.stats })
  const page = useQuery({ queryKey: ['matches', query], queryFn: () => api.matches(query), placeholderData: keepPreviousData })
  const years = (stats.data?.years ?? []).map((y) => y.value).filter((y) => /^\d{4}$/.test(y))
  const toggleRelease = (r: string) =>
    update({ release: query.release?.includes(r) ? query.release.filter((x) => x !== r) : [...(query.release ?? []), r] })

  return (
    <div className="layout">
      <aside className="filters" aria-label="Filters">
        <h2>Search</h2>
        {TEXT.map((k) => (
          <SearchBox
            key={k}
            label={{ q: 'Anything (team, player, server, file)', player: 'Player(s)', team: 'Team tag', steamid: 'SteamID' }[k]}
            placeholder={{ q: 'heaton + nuke', player: 'heaton|pott1  or  heaton + pott1', team: 'aAa|GG  or  aAa + GG', steamid: 'STEAM_0:1:12345' }[k]}
            value={(query[k] as string) ?? ''}
            onChange={(v) => update({ [k]: v })}
          />
        ))}
        <p className="hint">
          <code>|</code> any of them · <code>+</code> all in the same match (<code>aAa + GG</code>: their matches) · <code>*</code> anything in between (<code>k*l</code>) ·{' '}
          <code>"…"</code> exactly as typed, for names with <code>|</code> <code>+</code> <code>*</code> in them. SteamID: the whole ID.
        </p>
        <h2>Filters</h2>
        <div className="checks">
          {(stats.data?.releases ?? []).map((r) => (
            <label key={r.value}>
              <input type="checkbox" checked={query.release?.includes(r.value) ?? false} onChange={() => toggleRelease(r.value)} /> {r.value}{' '}
              <span className="sub">{r.count}</span>
            </label>
          ))}
        </div>
        <div className="row2">
          <label className="field">
            <span>Year from</span>
            <select value={query.year_from} onChange={(e) => update({ year_from: e.target.value })}>
              <option value="">any</option>
              {years.map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Year to</span>
            <select value={query.year_to} onChange={(e) => update({ year_to: e.target.value })}>
              <option value="">any</option>
              {years.map((y) => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="field">
          <span>Map</span>
          <select value={query.map} onChange={(e) => update({ map: e.target.value })}>
            <option value="">any map</option>
            {(stats.data?.maps ?? []).map((m) => (
              <option key={m.value} value={m.value}>
                {m.value} ({m.count})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Recording</span>
          <select value={query.pov} onChange={(e) => update({ pov: e.target.value })}>
            <option value="">any</option>
            <option value="hltv">HLTV</option>
            <option value="player">player POV</option>
          </select>
        </label>
        <button type="button" onClick={reset}>
          Reset all filters
        </button>
        <p className="hint">Years are filing estimates (HLTV stamp, demo file date or folder), not verified match dates. Hover a year to see its basis.</p>
      </aside>
      <section>
        <div className="toolbar">
          <strong>{page.data ? `${page.data.total.toLocaleString()} match${page.data.total === 1 ? '' : 'es'}` : 'Loading…'}</strong>
          {stats.data && (
            <span className="muted small">
              of {stats.data.matches.toLocaleString()} · {stats.data.demos.toLocaleString()} demos · {stats.data.rounds.toLocaleString()} rounds
            </span>
          )}
          <span className="spacer" />
          <label className="inline">
            Sort{' '}
            <select value={query.sort} onChange={(e) => update({ sort: e.target.value })}>
              <option value="date">year</option>
              <option value="release">release</option>
              <option value="map">map</option>
              <option value="team">team</option>
              <option value="kills">kills</option>
              <option value="duration">length</option>
            </select>
          </label>
          <button type="button" aria-label="Sort direction" onClick={() => update({ dir: query.dir === 'asc' ? 'desc' : 'asc' })}>
            {query.dir === 'asc' ? '▴' : '▾'}
          </button>
        </div>
        {page.isError && <p role="alert" className="error">Could not load matches: {String(page.error)}</p>}
        {page.data && <MatchTable items={page.data.items} />}
        {page.data && <Pager page={page.data.page} pages={Math.ceil(page.data.total / SIZE)} onPage={(p) => update({ page: p }, true)} />}
      </section>
    </div>
  )
}

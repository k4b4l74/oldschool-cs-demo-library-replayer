import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api, type MatchDemo } from '../api/client'
import { clock, KILL_LEAD, reason, ROUND_LEAD, sideClass } from '../format'
import PlayButton from './PlayButton'

/** Rounds of one demo with their kill feed. A round or a kill time starts the
 * game at that moment (the demo fast-forwards to it). */
export default function RoundsGrid({ demo }: { demo: MatchDemo }) {
  const q = useQuery({ queryKey: ['rounds', demo.sha1], queryFn: () => api.rounds(demo.sha1) })
  if (q.isPending) return <p className="muted">Loading rounds…</p>
  if (q.isError) return <p role="alert" className="error">Could not load rounds.</p>
  const { rounds, other_kills } = q.data
  if (!rounds.length) return <p className="muted">No round end found in this demo.</p>
  return (
    <>
      {other_kills > 0 && <p className="sub">{other_kills} kills outside rounds (warm-up)</p>}
      <div className="rounds-grid">
        {rounds.map((r) => (
          <div className="round" key={r.no}>
            <div className="rhead">
              <PlayButton demo={demo} seek={r.start - ROUND_LEAD} title={`Play this round (start: ${r.start_basis})`}>
                ▶ R{r.no}
              </PlayButton>
              <span className="clock">{clock(r.start)}</span>
              {r.winner ? <span className={`won ${sideClass(r.winner)}`}>{r.winner === 'CT' ? 'CT' : 'T'} win</span> : <span>draw</span>}
              <span className="why">{reason(r.reason)}</span>
              <span className="score">
                CT {r.score_ct ?? '?'} : T {r.score_t ?? '?'}
              </span>
            </div>
            {r.kills.length > 0 && (
              <ol className="feed">
                {r.kills.map((k, i) => (
                  <li key={i}>
                    <PlayButton demo={demo} seek={k.t - KILL_LEAD} className="clock" title={`Play from ${KILL_LEAD} s before this kill (demo ${clock(k.t)})`}>
                      {clock(Math.max(0, k.t - r.start))}
                    </PlayButton>
                    <Who id={k.killer_id} name={k.killer ?? 'world'} side={k.killer_side} />
                    <span className="wpn">{k.weapon}</span>
                    {k.headshot && <span className="hs">HS</span>}
                    <Who id={k.victim_id} name={k.victim ?? '?'} side={k.victim_side} />
                  </li>
                ))}
              </ol>
            )}
          </div>
        ))}
      </div>
    </>
  )
}

function Who({ id, name, side }: { id?: number | null; name: string; side?: string | null }) {
  const cls = `who ${sideClass(side)}`
  return id ? (
    <Link className={cls} to={`/player/${id}`} title={name}>
      {name}
    </Link>
  ) : (
    <span className={cls} title={name}>
      {name}
    </span>
  )
}

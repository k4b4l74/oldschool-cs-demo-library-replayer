import { useMutation } from '@tanstack/react-query'
import { api, type MatchDemo } from '../api/client'
import { clock } from '../format'
import { useToast } from './toast-context'

/** Starts the demo in its game install, optionally at ``seek`` (demo clock). */
export default function PlayButton({
  demo,
  seek,
  children,
  className = 'play',
  title,
}: {
  demo: Pick<MatchDemo, 'sha1' | 'engine' | 'play_problem'>
  seek?: number
  children: React.ReactNode
  className?: string
  title?: string
}) {
  const toast = useToast()
  const m = useMutation({
    mutationFn: () => api.play(demo.sha1, seek),
    onSuccess: (r) => {
      const at = r.seek ? ` at ${clock(r.seek)}` : ''
      toast('ok', `Starting ${r.release ?? 'the demo'}${at}`, [r.engine, r.window, r.seek_method && 'fast-forward first', r.map_note].filter(Boolean).join(' · '))
    },
    onError: (e: Error) => toast('error', 'Could not start the game', e.message),
  })
  if (!demo.engine) {
    return (
      <button type="button" className={`${className} off`} disabled title={demo.play_problem ?? 'no game install for this demo'}>
        {children}
      </button>
    )
  }
  return (
    <button
      type="button"
      className={className}
      disabled={m.isPending}
      title={title ?? `Play with ${demo.engine}`}
      onClick={(e) => {
        e.stopPropagation()
        m.mutate()
      }}
    >
      {children}
    </button>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../api/client'
import { useToast } from '../components/toast-context'

/** First start: where the games are, how to add demos. */
export default function Welcome() {
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const engines = useQuery({ queryKey: ['engines'], queryFn: api.engines })
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const imports = useQuery({ queryKey: ['imports'], queryFn: api.imports })
  const [folder, setFolder] = useState('')

  const addRoot = useMutation({
    mutationFn: (path: string) => api.saveSettings({ engine_roots: [...(settings.data?.engine_roots ?? []), path] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engines'] })
      qc.invalidateQueries({ queryKey: ['settings'] })
      setFolder('')
    },
    onError: (e: Error) => toast('error', 'Not saved', e.message),
  })
  const finish = useMutation({
    mutationFn: () => api.saveSettings({ welcomed: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      navigate('/')
    },
    onError: (e: Error) => toast('error', 'Not saved', e.message),
  })

  const installs = engines.data?.engines ?? []
  const ready = installs.filter((e) => e.enabled && e.status === 'ok')
  return (
    <article className="welcome">
      <h1>
        Welcome to Oldschool <span className="accent">CS</span> Demos
      </h1>
      <p className="lead">Your library of Counter-Strike 1.0 – 1.6 demos: find a match, a team or a player, then watch it in the game version it was recorded with, from the start or from any round.</p>

      <section className="panel step">
        <header className="panel-head">
          <h2>1 · The games</h2>
          <span className={`pill ${ready.length ? 'ok' : 'warning'}`}>{ready.length ? `${ready.length} ready` : 'none yet'}</span>
        </header>
        <p>
          Old demos only play in the game version that recorded them, so the app needs those versions installed (one folder per version, each with its <span className="mono">hl.exe</span>). Give
          the folder that contains them; the app looks inside and finds each version.
        </p>
        {ready.length > 0 && (
          <ul className="folders">
            {ready.map((e) => (
              <li key={e.id}>
                <b>{e.name}</b> <span className="sub">plays {e.release} demos</span>
              </li>
            ))}
          </ul>
        )}
        <form
          className="add-row"
          onSubmit={(e) => {
            e.preventDefault()
            if (folder.trim()) addRoot.mutate(folder.trim())
          }}
        >
          <input type="text" value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="E:\Games\Counter-Strike versions" className="mono" spellCheck={false} aria-label="Folder with game installs" />
          <button type="submit" disabled={addRoot.isPending}>
            {addRoot.isPending ? 'Looking…' : 'Look in this folder'}
          </button>
        </form>
        {settings.data && settings.data.effective_roots.length > 0 && (
          <p className="sub">
            Already looked in: {settings.data.effective_roots.map((r) => r.path).join(' · ')}. You can change this later in <Link to="/settings">Settings</Link>.
          </p>
        )}
        <p className="sub">No game installs? You can still browse the library; ▶ Play needs them.</p>
      </section>

      <section className="panel step">
        <header className="panel-head">
          <h2>2 · Your demos</h2>
        </header>
        <ul className="ways">
          <li>
            <b>Drag</b> demo files or archives (.dem, .zip, .rar, .7z, .ace…) onto this window, at any time.
          </li>
          <li>
            <b>Copy</b> them into the Drop folder{imports.data && <span className="mono"> {imports.data.drop_dir}</span>}: they are imported by themselves.
          </li>
          <li>
            <b>Import a folder</b> where you keep a collection, on the <Link to="/import">Import</Link> page.
          </li>
        </ul>
        <p className="sub">Each archive is opened (even archives inside archives), every map becomes a match, and teams, players, scores and rounds are read from the demos.</p>
      </section>

      <div className="toolbar">
        <button type="button" className="primary" onClick={() => finish.mutate()} disabled={finish.isPending}>
          Open the library
        </button>
      </div>
    </article>
  )
}

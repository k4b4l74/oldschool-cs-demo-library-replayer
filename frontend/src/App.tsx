import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router'
import { api } from './api/client'
import ThemeToggle from './components/ThemeToggle'
import { useToast } from './components/toast-context'
import { ToastProvider } from './components/Toasts'
import { useUploads } from './components/upload-context'
import { DropOverlay, UploadProvider } from './components/Uploads'
import { countsText, jobTitle } from './imports'
import Contact from './pages/Contact'
import Import from './pages/Import'
import Library from './pages/Library'
import Match from './pages/Match'
import Player from './pages/Player'
import Players from './pages/Players'
import Settings from './pages/Settings'
import Team from './pages/Team'
import Teams from './pages/Teams'
import Welcome from './pages/Welcome'

/** Nav entry for Import, with a live counter; tells when an import ends and refreshes the library. */
function ImportNav() {
  const q = useQuery({ queryKey: ['imports'], queryFn: api.imports, refetchInterval: (x) => (x.state.data?.active.length ? 1500 : 5000) })
  const uploads = useUploads()
  const toast = useToast()
  const qc = useQueryClient()
  const seen = useRef<Map<number, string> | null>(null)
  const active = q.data?.active ?? []
  useEffect(() => {
    if (!q.data) return
    const now = new Map(q.data.active.map((j) => [j.id, j.state]))
    if (seen.current) {
      const ended = [...seen.current.keys()].filter((id) => !now.has(id))
      for (const id of ended) {
        const j = q.data.recent.find((r) => r.id === id)
        if (j) toast(j.state === 'done' && !j.counts.failed ? 'ok' : j.state === 'done' ? 'info' : 'error', `${jobTitle(j)}: ${j.state}`, countsText(j))
      }
      if (ended.length) {
        // New matches, players and teams: everything shown may have changed.
        qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== 'imports' && x.queryKey[0] !== 'health' })
      }
    }
    seen.current = now
  }, [q.data, qc, toast])
  const running = active.find((j) => j.state === 'running')
  const label = running ? `${running.done}/${running.total}` : uploads.busy ? 'sending' : active.length ? `${active.length} waiting` : ''
  return (
    <NavLink to="/import">
      Import{label && <span className="badge">{label}</span>}
    </NavLink>
  )
}

/** First start: show the welcome page once, from the library's front page. */
function FirstRun() {
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const location = useLocation()
  const navigate = useNavigate()
  const done = useRef(false)
  useEffect(() => {
    if (done.current || !settings.data) return
    done.current = true
    if (!settings.data.welcomed && location.pathname === '/') navigate('/welcome', { replace: true })
  }, [settings.data, location.pathname, navigate])
  return null
}

function UploadsOverlay() {
  return <DropOverlay add={useUploads().add} />
}

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  return (
    <ToastProvider>
      <UploadProvider>
      <UploadsOverlay />
      <FirstRun />
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="Oldschool CS Demos, library">
          <span className="crosshair" aria-hidden="true" />
          <span>
            Oldschool <span className="accent">CS</span> Demos
            <small>Library · Replayer</small>
          </span>
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Library
          </NavLink>
          <NavLink to="/players">Players</NavLink>
          <NavLink to="/teams">Teams</NavLink>
          <ImportNav />
          <NavLink to="/settings">Settings</NavLink>
          <NavLink to="/contact">Contact</NavLink>
        </nav>
        <span className="spacer" />
        {health.isError && (
          <span role="alert" className="error">
            Backend not reachable
          </span>
        )}
        {health.data && <span className="muted small">v{health.data.version}</span>}
        <ThemeToggle />
      </header>
      <main className="shell">
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/match/:id" element={<Match />} />
          <Route path="/players" element={<Players />} />
          <Route path="/player/:id" element={<Player />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/team/:id" element={<Team />} />
          <Route path="/import" element={<Import />} />
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
      </UploadProvider>
    </ToastProvider>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { api, type Bind, type Engine, type EnginePatch, type EngineRoute, type Settings as SettingsT } from '../api/client'
import { useToast } from '../components/toast-context'
import { gameKey, gameMouse, keyLabel } from '../keys'

const PROTOCOLS = [43, 45, 46, 47, 48]
const RELEASES = ['CS1.0', 'CS1.1', 'CS1.3', 'CS1.4', 'CS1.5', 'CS1.6']
const SEEK = { framerate: 'speed up the engine (1.4, 1.5, 1.6)', retime: 'squeeze the demo clock (1.0, 1.1, 1.3)' }
const VIDEO = { registry: 'size from Settings below', 'registry-demo': "the demo's recorded size (1.3, 1.4)", args: 'size in the launch options (1.6)' }

function useSaver<T>(fn: (v: T) => Promise<unknown>, ok?: string) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['engines'] })
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['match'] })
      if (ok) toast('ok', ok)
    },
    onError: (e: Error) => toast('error', 'Not saved', e.message),
  })
}

function Status({ e }: { e: Engine }) {
  const label = !e.enabled ? 'off' : e.status === 'ok' ? 'ready' : e.status === 'warning' ? 'check' : 'broken'
  return <span className={`pill ${e.enabled ? e.status : 'off'}`}>{label}</span>
}

function Overridden({ e, field }: { e: Engine; field: keyof EnginePatch }) {
  return field in e.overrides ? <span className="edited" title={`detected: ${JSON.stringify(e.detected[field])}`}>edited</span> : null
}

function EngineEditor({ e }: { e: Engine }) {
  const save = useSaver((p: EnginePatch) => api.patchEngine(e.id, p), `${e.name} saved`)
  const [args, setArgs] = useState(e.args.join(' '))
  return (
    <div className="editor">
      <label className="field">
        <span>
          Network protocol <Overridden e={e} field="protocol" />
        </span>
        <select value={e.protocol ?? ''} onChange={(x) => save.mutate({ protocol: x.target.value ? Number(x.target.value) : null })}>
          <option value="">unknown</option>
          {PROTOCOLS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>
          CS release <Overridden e={e} field="release" />
        </span>
        <select value={e.release ?? ''} onChange={(x) => save.mutate({ release: x.target.value || null })}>
          <option value="">unknown</option>
          {RELEASES.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>
          Round jump <Overridden e={e} field="seek_method" />
        </span>
        <select value={e.seek_method ?? 'framerate'} onChange={(x) => save.mutate({ seek_method: x.target.value })}>
          {Object.entries(SEEK).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>
          Window size <Overridden e={e} field="video" />
        </span>
        <select value={e.video ?? 'registry'} onChange={(x) => save.mutate({ video: x.target.value })}>
          {Object.entries(VIDEO).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <label className="field wide">
        <span>
          Launch options <Overridden e={e} field="args" />
        </span>
        <input type="text" value={args} onChange={(x) => setArgs(x.target.value)} spellCheck={false} className="mono" />
      </label>
      <div className="editor-actions">
        <button type="button" onClick={() => save.mutate({ args: args.split(/\s+/).filter(Boolean) })}>
          Save options
        </button>
        {Object.keys(e.overrides).length > 0 && (
          <button
            type="button"
            className="ghost"
            onClick={() => save.mutate(Object.fromEntries(Object.keys(e.overrides).map((k) => [k, null])) as EnginePatch)}
          >
            Back to detected values
          </button>
        )}
      </div>
    </div>
  )
}

function EngineList({ engines }: { engines: Engine[] }) {
  const [open, setOpen] = useState<number | null>(null)
  const toggle = useSaver((e: Engine) => api.patchEngine(e.id, { enabled: !e.enabled }))
  const remove = useSaver((e: Engine) => api.deleteEngine(e.id), 'Install forgotten (files untouched)')
  if (!engines.length) return <p className="empty">No game install found yet: add a folder below or scan again.</p>
  return (
    <div className="table-wrap">
      <table className="results engines">
        <thead>
          <tr>
            <th>Install</th>
            <th>Plays</th>
            <th className="hide-sm">Engine</th>
            <th>State</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {engines.map((e) => (
            <EngineRows key={e.id} e={e} open={open === e.id} onOpen={() => setOpen(open === e.id ? null : e.id)} toggle={() => toggle.mutate(e)} remove={() => remove.mutate(e)} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EngineRows({ e, open, onOpen, toggle, remove }: { e: Engine; open: boolean; onOpen: () => void; toggle: () => void; remove: () => void }) {
  return (
    <>
      <tr className={e.enabled ? '' : 'disabled'}>
        <td>
          <b>{e.name}</b>
          <div className="mono sub">{e.path}</div>
        </td>
        <td>
          {e.release ?? '?'} <span className="sub">· protocol {e.protocol ?? '?'}</span>
        </td>
        <td className="hide-sm">
          {e.kind === 'won' ? `WON ${e.build ?? '?'}` : (e.build ?? '1.6 build ?')}
        </td>
        <td>
          <Status e={e} />
          {e.problems.map((p) => (
            <div key={p} className="problem">
              {p}
            </div>
          ))}
        </td>
        <td className="actions">
          <button type="button" onClick={onOpen} aria-expanded={open}>
            {open ? 'Close' : 'Edit'}
          </button>
          <button type="button" className="ghost" onClick={toggle}>
            {e.enabled ? 'Disable' : 'Enable'}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="editor-row">
          <td colSpan={5}>
            <EngineEditor e={e} />
            <p className="sub">
              Found by {e.source === 'scan' ? 'a folder scan' : 'hand'}. Forgetting it removes it from this list only; a scan finds it again if it is still in a scanned folder.{' '}
              <button type="button" className="link danger" onClick={remove}>
                Forget this install
              </button>
            </p>
          </td>
        </tr>
      )}
    </>
  )
}

function Routes({ routes, engines }: { routes: EngineRoute[]; engines: Engine[] }) {
  const save = useSaver((r: { route: EngineRoute; id: number | null }) => api.setRoute(r.route.protocol, r.route.release, r.id), 'Saved')
  const name = (id: number | null) => engines.find((e) => e.id === id)?.name ?? '—'
  if (!routes.length) return <p className="empty">No demo imported yet.</p>
  return (
    <table className="results routes">
      <thead>
        <tr>
          <th>Demos</th>
          <th>Played with</th>
          <th className="hide-sm">How</th>
        </tr>
      </thead>
      <tbody>
        {routes.map((r) => {
          const auto = r.chosen_id === null
          const others = engines.filter((e) => e.protocol === r.protocol && e.enabled)
          return (
            <tr key={`${r.protocol}-${r.release}`} className={r.engine_id ? '' : 'missing'}>
              <td>
                <b>{r.release}</b> <span className="sub">protocol {r.protocol}</span>
                <div className="sub">{r.demos.toLocaleString()} demos</div>
              </td>
              <td>
                <select
                  aria-label={`Install for ${r.release} protocol ${r.protocol}`}
                  value={auto ? '' : String(r.chosen_id)}
                  onChange={(x) => save.mutate({ route: r, id: x.target.value ? Number(x.target.value) : null })}
                >
                  <option value="">{r.engine_id && auto ? `Automatic: ${name(r.engine_id)}` : 'Automatic'}</option>
                  {others.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name} {e.release !== r.release ? `(${e.release})` : ''}
                    </option>
                  ))}
                </select>
              </td>
              <td className={`hide-sm ${r.engine_id ? 'sub' : 'problem'}`}>{r.how}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function FolderList({ title, values, onSave, placeholder }: { title: string; values: string[]; onSave: (v: string[]) => void; placeholder: string }) {
  const [draft, setDraft] = useState('')
  return (
    <div>
      <h3>{title}</h3>
      <ul className="folders">
        {values.map((v) => (
          <li key={v}>
            <span className="mono">{v}</span>
            <button type="button" className="link danger" onClick={() => onSave(values.filter((x) => x !== v))}>
              remove
            </button>
          </li>
        ))}
      </ul>
      <form
        className="add-row"
        onSubmit={(e) => {
          e.preventDefault()
          if (draft.trim()) onSave([...values, draft.trim()])
          setDraft('')
        }}
      >
        <input type="text" value={draft} placeholder={placeholder} onChange={(e) => setDraft(e.target.value)} spellCheck={false} className="mono" aria-label={`Add to ${title}`} />
        <button type="submit">Add</button>
      </form>
    </div>
  )
}

function GameSettings({ s }: { s: SettingsT }) {
  const save = useSaver((c: Partial<SettingsT>) => api.saveSettings(c), 'Settings saved')
  return (
    <div className="settings-grid">
      <label className="field">
        <span>Window size, CS 1.0–1.5</span>
        <select value={s.won_resolution} onChange={(e) => save.mutate({ won_resolution: e.target.value })}>
          {s.won_modes.map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
      </label>
      <label className="check">
        <input type="checkbox" checked={s.windowed} onChange={(e) => save.mutate({ windowed: e.target.checked })} /> Play in a window (not full screen)
      </label>
      <label className="field">
        <span>Fast-forward speed, CS 1.4–1.6 (demo seconds per frame)</span>
        <input type="number" min={0.05} max={5} step={0.05} defaultValue={s.seek_framerate} onBlur={(e) => save.mutate({ seek_framerate: Number(e.target.value) })} />
      </label>
      <label className="field">
        <span>Fast-forward factor, CS 1.0–1.3 (× faster)</span>
        <input type="number" min={2} max={100} step={1} defaultValue={s.seek_retime_factor} onBlur={(e) => save.mutate({ seek_retime_factor: Number(e.target.value) })} />
      </label>
    </div>
  )
}

type Target = { action: string; slot: number } | { own: number }
const sameTarget = (a: Target | null, b: Target) => JSON.stringify(a) === JSON.stringify(b)

/** The browser's keyboard layout (code → printed character), when it tells. */
function useLayout() {
  const [layout, setLayout] = useState<Map<string, string> | null>(null)
  useEffect(() => {
    const kb = (navigator as Navigator & { keyboard?: { getLayoutMap?: () => Promise<Map<string, string>> } }).keyboard
    kb?.getLayoutMap?.()
      .then((m) => setLayout(new Map(m)))
      .catch(() => setLayout(null))
  }, [])
  return layout
}

function KeyBox({ value, listening, label, layout, onStart, onKey, onCancel }: {
  value: string; listening: boolean; label: string; layout: Map<string, string> | null
  onStart: () => void; onKey: (k: string | null) => void; onCancel: () => void
}) {
  const took = useRef(false)
  return (
    <button
      type="button"
      className={`key ${listening ? 'listening' : ''} ${value ? '' : 'none'}`}
      aria-label={label}
      title={value ? `game key name: ${value}` : undefined}
      onClick={() => {
        if (took.current) took.current = false
        else if (listening) onCancel()
        else onStart()
      }}
      onBlur={() => listening && onCancel()}
      onKeyDown={(e) => {
        if (!listening) return
        e.preventDefault()
        if (e.code === 'Escape') onCancel()
        else if (e.code === 'Delete') onKey(null)
        else {
          const k = gameKey(e.code)
          if (k) onKey(k)
        }
      }}
      onMouseDown={(e) => {
        if (!listening) return
        e.preventDefault()
        took.current = true
        const k = gameMouse(e.button)
        if (k) onKey(k)
      }}
      onWheel={(e) => listening && onKey(e.deltaY < 0 ? 'mwheelup' : 'mwheeldown')}
      onContextMenu={(e) => listening && e.preventDefault()}
    >
      {listening ? 'press a key or button…' : value ? keyLabel(value, layout) : '—'}
    </button>
  )
}

function Controls({ s }: { s: SettingsT }) {
  const save = useSaver((c: { controls: Record<string, string[]>; binds: Bind[] }) => api.saveSettings(c), 'Keys saved')
  const layout = useLayout()
  const pad = (keys: string[] | undefined) => [keys?.[0] ?? '', keys?.[1] ?? '']
  const fromSaved = () => Object.fromEntries(s.actions.map((a) => [a.id, pad(s.controls[a.id])]))
  const [keys, setKeys] = useState<Record<string, string[]>>(fromSaved)
  const [own, setOwn] = useState<Bind[]>(s.binds)
  const [capture, setCapture] = useState<Target | null>(null)

  const assign = (t: Target, k: string | null) => {
    // Like the game: a key used elsewhere moves here.
    const nextKeys = Object.fromEntries(Object.entries(keys).map(([a, ks]) => [a, ks.map((x) => (k && x === k ? '' : x))]))
    const nextOwn = own.map((b) => (k && b.key === k ? { ...b, key: '' } : b))
    if ('action' in t) nextKeys[t.action] = nextKeys[t.action].map((x, i) => (i === t.slot ? (k ?? '') : x))
    else nextOwn[t.own] = { ...nextOwn[t.own], key: k ?? '' }
    setKeys(nextKeys)
    setOwn(nextOwn)
    setCapture(null)
  }
  const box = (t: Target, value: string, label: string) => (
    <KeyBox value={value} label={label} layout={layout} listening={sameTarget(capture, t)} onStart={() => setCapture(t)} onCancel={() => setCapture(null)} onKey={(k) => assign(t, k)} />
  )

  const controls = Object.fromEntries(Object.entries(keys).map(([a, ks]) => [a, ks.filter(Boolean)]))
  const binds = own.map((b) => ({ key: b.key, command: b.command.trim() }))
  const changed = JSON.stringify({ controls, binds }) !== JSON.stringify({ controls: Object.fromEntries(s.actions.map((a) => [a.id, s.controls[a.id] ?? []])), binds: s.binds })
  const ownReady = binds.every((b) => b.key && b.command && !b.command.includes('"'))
  const defaults = () => {
    const taken = new Set(own.map((b) => b.key))
    setKeys(Object.fromEntries(s.actions.map((a) => [a.id, pad(a.defaults.filter((k) => !taken.has(k)))])))
  }

  return (
    <div className="controls">
      <p className="sub">
        The same keys in every game version: before each ▶ Play the app writes them to <span className="mono">cstrike\oldschool.cfg</span> in the install that plays the demo. Click a key, then press
        the new key or mouse button (Delete clears it, Escape cancels). Keys are shown as printed on your keyboard: the game reads where a key is, so on a French keyboard the game's W A S D are your Z Q S D.
      </p>
      <div className="table-wrap">
        <table className="results controls-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Key / button</th>
              <th>Alternate</th>
            </tr>
          </thead>
          {s.control_groups.map((g) => (
            <tbody key={g.id}>
              <tr className="group">
                <th colSpan={3}>
                  {g.label}
                  {g.hint && <div className="sub">{g.hint}</div>}
                </th>
              </tr>
              {s.actions
                .filter((a) => a.group === g.id)
                .map((a) => (
                  <tr key={a.id}>
                    <td title={a.command}>
                      {a.label}
                      {a.hint && <span className="sub"> · {a.hint}</span>}
                    </td>
                    <td>{box({ action: a.id, slot: 0 }, keys[a.id][0], `${a.label}: key`)}</td>
                    <td>{box({ action: a.id, slot: 1 }, keys[a.id][1], `${a.label}: alternate`)}</td>
                  </tr>
                ))}
            </tbody>
          ))}
          <tbody>
            <tr className="group">
              <th colSpan={3}>
                Your own commands
                <div className="sub">Any console command; several commands: separate them with ;</div>
              </th>
            </tr>
            {own.map((b, i) => (
              <tr key={i}>
                <td>
                  <input type="text" className="mono" value={b.command} onChange={(e) => setOwn(own.map((x, j) => (j === i ? { ...x, command: e.target.value } : x)))} placeholder="say gg" spellCheck={false} aria-label={`Own command ${i + 1}`} />
                </td>
                <td>{box({ own: i }, b.key, `Own command ${i + 1}: key`)}</td>
                <td>
                  <button type="button" className="link danger" onClick={() => setOwn(own.filter((_, j) => j !== i))}>
                    remove
                  </button>
                </td>
              </tr>
            ))}
            <tr>
              <td colSpan={3}>
                <button type="button" onClick={() => setOwn([...own, { key: '', command: '' }])}>
                  Add a command
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="toolbar">
        <button type="button" className="primary" disabled={!changed || !ownReady || save.isPending} onClick={() => save.mutate({ controls, binds })}>
          Save keys
        </button>
        <button type="button" onClick={defaults}>
          Back to the default keys
        </button>
        {changed && (
          <button type="button" className="ghost" onClick={() => { setKeys(fromSaved()); setOwn(s.binds) }}>
            Cancel changes
          </button>
        )}
        {changed && <span className="sub">{ownReady ? 'not saved yet' : 'each own command needs a key, and no "'}</span>}
      </div>
    </div>
  )
}

export default function Settings() {
  const engines = useQuery({ queryKey: ['engines'], queryFn: api.engines })
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings })
  const scan = useSaver(() => api.scanEngines(), 'Scan done')
  const add = useSaver((p: string) => api.addEngine(p), 'Install added')
  const saveRoots = useSaver((roots: string[]) => api.saveSettings({ engine_roots: roots }), 'Folders saved')
  const saveMaps = useSaver((m: string[]) => api.saveSettings({ map_folders: m }), 'Map folders saved')
  const [path, setPath] = useState('')
  return (
    <article className="settings">
      <h1>Settings</h1>
      <section className="panel">
        <header className="panel-head">
          <h2>Game installs</h2>
          <button type="button" onClick={() => scan.mutate(undefined)} disabled={scan.isPending}>
            {scan.isPending ? 'Scanning…' : 'Scan folders again'}
          </button>
        </header>
        <p className="sub">Every folder with an hl.exe inside the scanned folders below. What was detected can be changed with Edit.</p>
        {engines.data && <EngineList engines={engines.data.engines} />}
        <form
          className="add-row"
          onSubmit={(e) => {
            e.preventDefault()
            if (path.trim()) add.mutate(path.trim())
            setPath('')
          }}
        >
          <input type="text" value={path} onChange={(e) => setPath(e.target.value)} placeholder="Add one install: E:\Games\CS15_P46_hl1110" className="mono" spellCheck={false} aria-label="Install folder" />
          <button type="submit">Add install</button>
        </form>
      </section>
      <section className="panel">
        <header className="panel-head">
          <h2>Which install plays which demos</h2>
        </header>
        <p className="sub">One line per kind of demo in your library. The engine must speak the demo's network protocol; Automatic picks the same CS release, newest build first.</p>
        {engines.data && <Routes routes={engines.data.routes} engines={engines.data.engines} />}
      </section>
      {settings.data && (
        <>
          <section className="panel">
            <header className="panel-head">
              <h2>Folders</h2>
            </header>
            <div className="two-col">
              <div>
                <h3>Scanned for game installs</h3>
                <ul className="folders">
                  {settings.data.effective_roots.map((r) => (
                    <li key={r.path}>
                      <span className="mono">{r.path}</span> <span className="tag">{r.source}</span>
                      {!r.exists && <span className="problem"> not found</span>}
                    </li>
                  ))}
                </ul>
                <FolderList title="Your folders" values={settings.data.engine_roots} onSave={(v) => saveRoots.mutate(v)} placeholder="E:\Games\CS installs" />
              </div>
              <FolderList
                title="Extra map folders (for a missing .bsp)"
                values={settings.data.map_folders}
                onSave={(v) => saveMaps.mutate(v)}
                placeholder="E:\Games\maps"
              />
            </div>
          </section>
          <section className="panel">
            <header className="panel-head">
              <h2>Game window and round jump</h2>
            </header>
            <GameSettings s={settings.data} />
          </section>
          <section className="panel">
            <header className="panel-head">
              <h2>Keys in the game</h2>
            </header>
            <Controls s={settings.data} />
          </section>
          <p className="sub">
            Library data: <span className="mono">{settings.data.data_dir}</span>
          </p>
        </>
      )}
    </article>
  )
}

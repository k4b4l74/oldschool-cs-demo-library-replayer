import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { api, type ImportsView, type Job, type JobFile } from '../api/client'
import Pager from '../components/Pager'
import { useToast } from '../components/toast-context'
import { useUploads } from '../components/upload-context'
import { splitDropped } from '../components/upload-context'
import { countsText, jobTitle, mb, when } from '../imports'

const STATUS_LABEL: Record<string, string> = {
  imported: 'imported',
  reanalysed: 'read again',
  already: 'already in library',
  'no-demo': 'no demo inside',
  failed: 'failed',
  missing: 'file gone',
}
const STATUS_CLASS: Record<string, string> = { imported: 'ok', reanalysed: 'ok', already: 'off', 'no-demo': 'warning', failed: 'broken', missing: 'warning' }
const STATE_CLASS: Record<string, string> = { done: 'ok', running: 'warning', queued: 'off', failed: 'broken', cancelled: 'off' }

function useAction<T>(fn: (v: T) => Promise<unknown>, ok?: string) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['imports'] })
      qc.invalidateQueries({ queryKey: ['import'] })
      if (ok) toast('ok', ok)
    },
    onError: (e: Error) => toast('error', 'Not done', e.message),
  })
}

function AddDemos({ view }: { view: ImportsView }) {
  const uploads = useUploads()
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const toast = useToast()
  const open = useAction(() => api.openDrop())
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Add demos</h2>
      </header>
      <div
        className={`dropzone${over ? ' over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          e.stopPropagation() // handled here, not by the page-wide overlay
          setOver(false)
          const { files, folders } = splitDropped(e.dataTransfer)
          if (folders.length) toast('error', `Folders cannot be sent from the browser (${folders.join(', ')})`, 'Use “Import a folder” below, or copy the folder into the Drop folder.')
          if (files.length) uploads.add(files)
        }}
      >
        <b>Drag demos or archives here</b>
        <span className="sub">.dem, .zip, .rar, .7z, .ace and other archives, even nested; several maps in one archive become several matches</span>
        <button type="button" onClick={() => input.current?.click()}>
          Choose files…
        </button>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          aria-label="Choose demo files"
          onChange={(e) => {
            uploads.add(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
      </div>
      {uploads.items.length > 0 && (
        <ul className="uploads">
          {uploads.items.map((u) => (
            <li key={u.id} className={u.state}>
              <span className="mono">{u.name}</span>
              <span className="sub">{mb(u.size)}</span>
              {u.state === 'sending' && <progress max={u.size || 1} value={u.sent} aria-label={`Sending ${u.name}`} />}
              <span className={u.state === 'error' ? 'problem' : 'sub'}>{u.state === 'error' ? u.message : u.state === 'sent' ? 'sent · result in Recent imports' : u.state}</span>
            </li>
          ))}
          {!uploads.busy && (
            <li>
              <button type="button" className="link" onClick={uploads.clear}>
                clear this list
              </button>
            </li>
          )}
        </ul>
      )}
      <p className="sub drop-folder">
        Or put files in the Drop folder: <span className="mono">{view.drop_dir}</span>{' '}
        <button type="button" className="link" onClick={() => open.mutate(undefined)}>
          open it
        </button>
        <br />
        They are imported a few seconds after they stop changing, then kept by the app and removed from the Drop folder. Nothing is deleted: files that cannot be imported are moved
        to its <span className="mono">_failed</span> (with a .txt saying why), <span className="mono">_already imported</span> or <span className="mono">_skipped</span> sub-folders.
      </p>
    </section>
  )
}

function Progress({ j }: { j: Job }) {
  const cancel = useAction((id: number) => api.cancelImport(id), 'Stopping…')
  const pct = j.total ? Math.round((100 * j.done) / j.total) : 0
  return (
    <div className="job-live">
      <div className="job-line">
        <span className={`pill ${STATE_CLASS[j.state]}`}>{j.state === 'running' ? 'running' : 'waiting'}</span>
        <b>{jobTitle(j)}</b>
        <span className="spacer" />
        <button type="button" className="ghost" onClick={() => cancel.mutate(j.id)}>
          Stop
        </button>
      </div>
      {j.state === 'running' && (
        <>
          <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={j.total} aria-valuenow={j.done} aria-label={`Import ${j.id}`}>
            <span style={{ width: `${pct}%` }} />
          </div>
          <div className="sub">
            <span className="hud">
              {j.done.toLocaleString()} / {j.total.toLocaleString()}
            </span>{' '}
            files · {countsText(j)}
            {j.current && (
              <>
                {' '}
                · <span className="mono">{j.current}</span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function FolderImport({ view }: { view: ImportsView }) {
  const [path, setPath] = useState('')
  const [copy, setCopy] = useState(true)
  const add = useAction((v: { path: string; copy: boolean }) => api.importFolder(v.path, v.copy), 'Import queued')
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Import a folder on this PC</h2>
      </header>
      <p className="sub">For a demo collection you keep where it is (sub-folders included). The files are not moved. Running it again later only reads the new files.</p>
      <form
        className="add-row"
        onSubmit={(e) => {
          e.preventDefault()
          if (path.trim()) add.mutate({ path: path.trim(), copy })
        }}
      >
        <input type="text" value={path} onChange={(e) => setPath(e.target.value)} placeholder="E:\Demos\CS 1.5" className="mono" spellCheck={false} aria-label="Folder to import" />
        <button type="submit" disabled={add.isPending}>
          Import
        </button>
      </form>
      <div className="choices" role="radiogroup" aria-label="Demo copies">
        <label className="check">
          <input type="radio" name="copy" checked={copy} onChange={() => setCopy(true)} /> Copy the demos into the library (safe if the folder moves later; compressed copies)
        </label>
        <label className="check">
          <input type="radio" name="copy" checked={!copy} onChange={() => setCopy(false)} /> Read the demos from this folder when played (no extra disk space; keep the folder where it is)
        </label>
      </div>
      {view.folders.length > 0 && (
        <>
          <h3>Folders imported</h3>
          <ul className="folders">
            {view.folders.map((f) => (
              <li key={f.path}>
                <span className="mono">{f.path}</span>
                <span className="tag">{f.copy_demos ? 'copied' : 'read in place'}</span>
                <span className="sub">last {when(f.last_run)}</span>
                <button type="button" className="link" onClick={() => add.mutate({ path: f.path, copy: f.copy_demos })}>
                  check for new files
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function FileRow({ f }: { f: JobFile }) {
  const retry = useAction((id: number) => api.retryFile(id), 'Retry queued')
  return (
    <tr>
      <td>
        <span className={`pill ${STATUS_CLASS[f.status] ?? ''}`}>{STATUS_LABEL[f.status] ?? f.status}</span>
      </td>
      <td>
        <span className="mono">{f.label}</span>
        {f.moved_to && <div className="sub">moved to {f.moved_to}</div>}
        {f.message && <pre className={f.status === 'failed' ? 'message problem' : 'message sub'}>{f.message}</pre>}
      </td>
      <td>
        {f.matches.map((m) => (
          <div key={m.id}>
            <Link to={`/match/${m.id}`}>{m.name}</Link>
          </div>
        ))}
      </td>
      <td className="actions">
        {f.status === 'failed' &&
          (f.retry_job_id ? (
            <span className="sub">retried (#{f.retry_job_id})</span>
          ) : (
            <button type="button" onClick={() => retry.mutate(f.id)} disabled={retry.isPending}>
              Retry
            </button>
          ))}
      </td>
    </tr>
  )
}

function JobFiles({ j }: { j: Job }) {
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const q = useQuery({
    queryKey: ['import', j.id, status, page],
    queryFn: () => api.importDetail(j.id, status || undefined, page),
    refetchInterval: j.state === 'running' ? 2000 : false,
  })
  if (!q.data) return <p className="sub">{q.isError ? 'Could not load the files.' : 'Loading…'}</p>
  const d = q.data
  const all = Object.values(d.status_counts).reduce((a, b) => a + b, 0)
  return (
    <div className="job-files">
      <div className="checks" role="group" aria-label="Show">
        {[['', `all ${all}`], ...Object.entries(d.status_counts).map(([k, n]) => [k, `${STATUS_LABEL[k] ?? k} ${n}`])].map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={status === k ? 'on' : 'ghost'}
            aria-pressed={status === k}
            onClick={() => {
              setStatus(k)
              setPage(1)
            }}
          >
            {label}
          </button>
        ))}
      </div>
      {d.files.length === 0 ? (
        <p className="sub">{j.kind === 'import' && j.counts.already ? 'All the files were already in the library.' : 'No file.'}</p>
      ) : (
        <div className="table-wrap">
          <table className="results files">
            <thead>
              <tr>
                <th>Result</th>
                <th>File</th>
                <th>Matches</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.files.map((f) => (
                <FileRow key={f.id} f={f} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={d.page} pages={Math.ceil(d.total_files / d.size)} onPage={setPage} />
    </div>
  )
}

function Recent({ jobs }: { jobs: Job[] }) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Recent imports</h2>
      </header>
      {jobs.length === 0 ? (
        <p className="empty">Nothing imported from the app yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="results jobs">
            <thead>
              <tr>
                <th>#</th>
                <th>What</th>
                <th>Result</th>
                <th className="hide-sm">Finished</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <JobRows key={j.id} j={j} open={open === j.id} onOpen={() => setOpen(open === j.id ? null : j.id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function JobRows({ j, open, onOpen }: { j: Job; open: boolean; onOpen: () => void }) {
  return (
    <>
      <tr className="row" onClick={onOpen}>
        <td className="sub">{j.id}</td>
        <td>
          <b className="mono">{jobTitle(j)}</b>
        </td>
        <td>
          <span className={`pill ${STATE_CLASS[j.state]}`}>{j.state}</span> <span className={j.counts.failed ? 'problem' : ''}>{countsText(j)}</span>
          {j.error && <div className="problem">{j.error}</div>}
        </td>
        <td className="hide-sm sub">{when(j.finished_at)}</td>
        <td className="actions">
          <button type="button" aria-expanded={open} onClick={(e) => (e.stopPropagation(), onOpen())}>
            {open ? 'Close' : 'Files'}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="editor-row">
          <td colSpan={5}>
            <JobFiles j={j} />
          </td>
        </tr>
      )}
    </>
  )
}

function Reanalyse({ view }: { view: ImportsView }) {
  const run = useAction((only: boolean) => api.reanalyse(only), 'Re-analysis queued')
  const busy = view.active.some((j) => j.kind === 'reanalyse')
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Re-analyse the library</h2>
      </header>
      <p className="sub">
        Reads every file of the library again with this version of the app, to pick up improvements in how teams, scores and rounds are read. Your files are not changed. Matches
        get new numbers, so saved links to a match may stop working. Files that are gone keep their current data.
      </p>
      <p>
        {view.library_files.toLocaleString()} files in the library
        {view.outdated_files > 0 ? `, ${view.outdated_files.toLocaleString()} read by an older version` : ', all read by this version'}.
      </p>
      <div className="toolbar">
        <button type="button" disabled={busy || view.outdated_files === 0} onClick={() => run.mutate(true)}>
          Re-analyse the older ones
        </button>
        <button
          type="button"
          className="ghost"
          disabled={busy || view.library_files === 0}
          onClick={() => {
            if (window.confirm(`Read all ${view.library_files.toLocaleString()} files again? This can take hours on a big library; it can be stopped.`)) run.mutate(false)
          }}
        >
          Re-analyse everything
        </button>
        {busy && <span className="sub">running…</span>}
      </div>
    </section>
  )
}

export default function Import() {
  const q = useQuery({ queryKey: ['imports'], queryFn: api.imports, refetchInterval: (x) => (x.state.data?.active.length ? 1000 : 4000) })
  if (!q.data) return <p className="muted">{q.isError ? 'Backend not reachable.' : 'Loading…'}</p>
  const view = q.data
  return (
    <article className="import">
      <h1>Import</h1>
      <AddDemos view={view} />
      {view.active.length > 0 && (
        <section className="panel">
          <header className="panel-head">
            <h2>In progress</h2>
          </header>
          {view.active.map((j) => (
            <Progress key={j.id} j={j} />
          ))}
        </section>
      )}
      {view.open_failures > 0 && (
        <p className="problem">
          {view.open_failures} file{view.open_failures > 1 ? 's' : ''} could not be imported: open the import below to see why and retry.
        </p>
      )}
      <Recent jobs={view.recent} />
      <FolderImport view={view} />
      <Reanalyse view={view} />
    </article>
  )
}

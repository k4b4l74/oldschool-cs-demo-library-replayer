import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { ImportsView, Job, JobDetail } from '../api/client'
import { ToastProvider } from '../components/Toasts'
import { UploadProvider } from '../components/Uploads'
import { mockApi, renderAt } from '../test-utils'
import Import from './Import'

afterEach(() => vi.unstubAllGlobals())

const counts = { imported: 0, already: 0, no_demo: 0, failed: 0, matches: 0, demos_new: 0 }
const job = (id: number, extra: Partial<Job> = {}): Job => ({
  id, kind: 'import', origin: 'drop', state: 'done', paths: ['C:\\Data\\Drop\\aaa.zip'], copy_demos: true, done: 0, total: 0, current: null,
  counts, error: null, created_at: '2026-11-12T10:00:00Z', started_at: null, finished_at: '2026-11-12T10:01:00Z', ...extra,
})

const view: ImportsView = {
  drop_dir: 'C:\\Users\\x\\AppData\\Local\\OldschoolCSDemos\\Drop',
  active: [job(9, { state: 'running', origin: 'folder', paths: ['E:\\Demos'], done: 120, total: 400, current: '2002/aaa_vs_gg.zip', counts: { ...counts, imported: 118, matches: 130 } })],
  recent: [job(7, { counts: { ...counts, imported: 2, matches: 3, failed: 1 } })],
  folders: [{ path: 'E:\\Demos', copy_demos: false, last_job_id: 9, last_run: '2026-11-12T10:00:00Z' }],
  open_failures: 1,
  outdated_files: 0,
  library_files: 41000,
}

const detail: JobDetail = {
  job: view.recent[0], status_counts: { imported: 2, failed: 1 }, total_files: 3, page: 1, size: 50,
  files: [
    { id: 31, path: 'C:\\x\\locked.zip', label: 'locked.zip', status: 'failed', matches: [], demos_new: 0, message: 'PermissionError: denied', moved_to: 'C:\\Data\\Drop\\_failed\\locked.zip', retry_job_id: null, original_id: null },
    { id: 32, path: 'C:\\x\\aaa.zip', label: 'aaa.zip', status: 'imported', matches: [{ id: 5, name: '[aAa]_[GG]_[de_dust2]_[HLTV]_[ctt].zip' }], demos_new: 2, message: null, moved_to: null, retry_job_id: null, original_id: 4 },
  ],
}

const page = () => (
  <ToastProvider>
    <UploadProvider>
      <Import />
    </UploadProvider>
  </ToastProvider>
)

test('shows progress, failures with a retry, and folders to check again', async () => {
  mockApi({ '/api/imports': view, '/api/imports/7': detail, '/api/imports/files/31/retry': job(10, { state: 'queued' }) })
  renderAt('/import', '/import', page())
  expect(await screen.findByText('Folder E:\\Demos', { selector: 'b' })).toBeInTheDocument()
  expect(screen.getByRole('progressbar', { name: 'Import 9' })).toHaveAttribute('aria-valuenow', '120')
  expect(screen.getByText('2002/aaa_vs_gg.zip')).toBeInTheDocument()
  expect(screen.getByText(/1 file could not be imported/)).toBeInTheDocument()
  expect(screen.getByText(/C:\\Users\\x\\AppData\\Local\\OldschoolCSDemos\\Drop/)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Files' }))
  expect(await screen.findByText('PermissionError: denied')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '[aAa]_[GG]_[de_dust2]_[HLTV]_[ctt].zip' })).toHaveAttribute('href', '/match/5')
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
  await waitFor(() => {
    const post = vi.mocked(fetch).mock.calls.find(([url, init]) => init?.method === 'POST' && String(url).includes('retry'))
    expect(post?.[0]).toBe('/api/imports/files/31/retry')
    const headers = (post?.[1]?.headers ?? {}) as Record<string, string>
    expect(headers['X-Oldschool']).toBe('1')
  })

  const folders = screen.getByText('Folders imported').nextElementSibling as HTMLElement
  expect(within(folders).getByText('read in place')).toBeInTheDocument()
  fireEvent.click(within(folders).getByRole('button', { name: 'check for new files' }))
  await waitFor(() => {
    const post = vi.mocked(fetch).mock.calls.find(([url, init]) => init?.method === 'POST' && url === '/api/imports')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ path: 'E:\\Demos', copy_demos: false })
  })
})

test('import a folder with the chosen copy option', async () => {
  mockApi({ '/api/imports': { ...view, active: [], folders: [] } })
  renderAt('/import', '/import', page())
  const input = await screen.findByRole('textbox', { name: 'Folder to import' })
  fireEvent.change(input, { target: { value: 'E:\\CS\\sorted\\CS1.5' } })
  fireEvent.click(screen.getByRole('radio', { name: /Read the demos from this folder/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Import' }))
  await waitFor(() => {
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ path: 'E:\\CS\\sorted\\CS1.5', copy_demos: false })
  })
  expect(screen.getByRole('button', { name: 'Re-analyse the older ones' })).toBeDisabled()
})

class FakeXhr {
  static sent: { url: string; headers: Record<string, string>; body: File }[] = []
  url = ''
  headers: Record<string, string> = {}
  status = 0
  responseText = ''
  upload = { onprogress: null as null | ((e: { loaded: number }) => void) }
  onload: null | (() => void) = null
  onerror: null | (() => void) = null
  open(_m: string, url: string) {
    this.url = url
  }
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v
  }
  send(body: File) {
    FakeXhr.sent.push({ url: this.url, headers: this.headers, body })
    this.upload.onprogress?.({ loaded: body.size })
    this.status = 200
    this.responseText = JSON.stringify({ name: body.name, size: body.size })
    setTimeout(() => this.onload?.(), 0)
  }
}

test('chosen files are sent to the Drop folder; other files are refused here', async () => {
  FakeXhr.sent = []
  vi.stubGlobal('XMLHttpRequest', FakeXhr)
  mockApi({ '/api/imports': { ...view, active: [] } })
  renderAt('/import', '/import', page())
  const picker = await screen.findByLabelText('Choose demo files')
  const demo = new File(['HLDEMO'], 'aaa vs gg.dem')
  const photo = new File(['x'], 'team.jpg')
  fireEvent.change(picker, { target: { files: [demo, photo] } })
  expect(await screen.findByText(/not a demo \(\.dem\) or an archive/)).toBeInTheDocument()
  expect(await screen.findByText('sent · result in Recent imports')).toBeInTheDocument()
  expect(FakeXhr.sent.map((s) => s.url)).toEqual(['/api/drop?name=aaa%20vs%20gg.dem'])
  expect(FakeXhr.sent[0].headers['X-Oldschool']).toBe('1')
})

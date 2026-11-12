import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { EnginesView, Settings as SettingsT } from '../api/client'
import { ToastProvider } from '../components/Toasts'
import { mockApi, renderAt } from '../test-utils'
import Welcome from './Welcome'

afterEach(() => vi.unstubAllGlobals())

const settings: SettingsT = {
  engine_roots: [], map_folders: [], won_resolution: '1280x960', windowed: true, seek_framerate: 0.5, seek_retime_factor: 20, welcomed: false, binds: [], controls: {}, actions: [], control_groups: [],
  effective_roots: [{ path: 'C:\\Users\\x\\AppData\\Local\\OldschoolCSDemos\\Engines', source: 'default', exists: true }],
  won_modes: ['1280x960'], data_dir: 'C:\\Users\\x\\AppData\\Local\\OldschoolCSDemos',
}
const empty: EnginesView = { engines: [], routes: [] }

test('first start: give the games folder, then open the library', async () => {
  mockApi({ '/api/engines': empty, '/api/settings': settings, '/api/imports': { drop_dir: 'C:\\Data\\Drop', active: [], recent: [], folders: [], open_failures: 0, outdated_files: 0, library_files: 0 } })
  renderAt('/welcome', '/welcome', <ToastProvider><Welcome /></ToastProvider>)
  expect(await screen.findByText('none yet')).toBeInTheDocument()
  expect(await screen.findByText(/C:\\Data\\Drop/)).toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox', { name: 'Folder with game installs' }), { target: { value: 'E:\\Games\\CS' } })
  fireEvent.click(screen.getByRole('button', { name: 'Look in this folder' }))
  await waitFor(() => {
    const put = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ engine_roots: ['E:\\Games\\CS'] })
  })
  fireEvent.click(screen.getByRole('button', { name: 'Open the library' }))
  await waitFor(() => {
    const puts = vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PUT')
    expect(JSON.parse(String(puts.at(-1)?.[1]?.body))).toEqual({ welcomed: true })
  })
})

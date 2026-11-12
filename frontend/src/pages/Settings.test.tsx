import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import type { Engine, EnginesView, Settings as SettingsT } from '../api/client'
import { ToastProvider } from '../components/Toasts'
import { mockApi, renderAt } from '../test-utils'
import Settings from './Settings'

afterEach(() => vi.unstubAllGlobals())

const engine = (id: number, name: string, extra: Partial<Engine> = {}): Engine => ({
  id, name, path: `E:\\CounterStrike\\game\\installed\\${name}`, source: 'scan', enabled: true, missing: false, status: 'ok', problems: [],
  kind: 'steam', build: 'build 3248', protocol: 47, release: 'CS1.6', seek_method: 'framerate', video: 'args', args: ['-game', 'cstrike'],
  detected: {}, overrides: {}, ...extra,
})

const view: EnginesView = {
  engines: [
    engine(1, 'CS16_P47_build2603', { build: 'build 2603' }),
    engine(2, 'CS16_P47_build3248'),
    engine(3, 'CS11_P43_hl1106', { kind: 'won', build: '1.1.0.6', protocol: 43, release: 'CS1.1', status: 'broken', problems: ['hw.dll missing'] }),
  ],
  routes: [
    { protocol: 47, release: 'CS1.6', demos: 27264, engine_id: 2, chosen_id: null, how: 'automatic', candidate_ids: [2, 1] },
    { protocol: 43, release: 'CS1.1', demos: 140, engine_id: null, chosen_id: null, how: 'no working install for CS1.1 (network protocol 43): add one in Settings', candidate_ids: [] },
  ],
}

const settings: SettingsT = {
  engine_roots: [], map_folders: [], won_resolution: '1280x960', windowed: true, seek_framerate: 0.5, seek_retime_factor: 20, welcomed: true, binds: [{ key: 'f9', command: 'say gg' }],
  controls: { forward: ['w', 'uparrow'], jump: ['space'], snapshot: ['f5'] },
  actions: [
    { id: 'forward', group: 'camera', label: 'Move forward', command: '+forward', defaults: ['w', 'uparrow'], hint: '' },
    { id: 'jump', group: 'camera', label: 'Jump', command: '+jump', defaults: ['space'], hint: 'changes the camera mode' },
    { id: 'snapshot', group: 'demo', label: 'Screenshot', command: 'snapshot', defaults: ['f5'], hint: '' },
  ],
  control_groups: [{ id: 'camera', label: 'Camera (HLTV demos)', hint: '' }, { id: 'demo', label: 'Watching', hint: '' }],
  effective_roots: [{ path: 'E:\\CounterStrike\\game\\installed', source: 'environment', exists: true }],
  won_modes: ['1024x768', '1280x960'], data_dir: 'C:\\Users\\x\\AppData\\Local\\OldschoolCSDemos',
}

test('lists installs with their state and changes which install plays a kind of demo', async () => {
  mockApi({ '/api/engines': view, '/api/settings': settings, '/api/routes': view })
  renderAt('/settings', '/settings', <ToastProvider><Settings /></ToastProvider>)
  expect(await screen.findByText('CS16_P47_build3248', { selector: 'b' })).toBeInTheDocument()
  expect(screen.getByText('hw.dll missing')).toBeInTheDocument()
  expect(screen.getByText('broken')).toBeInTheDocument()
  expect(screen.getByText(/no working install for CS1.1/)).toBeInTheDocument()
  const select = screen.getByRole('combobox', { name: 'Install for CS1.6 protocol 47' })
  expect(screen.getByRole('option', { name: 'Automatic: CS16_P47_build3248' })).toBeInTheDocument()
  fireEvent.change(select, { target: { value: '1' } })
  await waitFor(() => {
    const put = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PUT')
    expect(put?.[0]).toBe('/api/routes')
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ protocol: 47, release: 'CS1.6', engine_id: 1 })
  })
  expect(await screen.findByText('E:\\CounterStrike\\game\\installed')).toBeInTheDocument()
})

test('editing an install sends only the changed field', async () => {
  mockApi({ '/api/engines': view, '/api/settings': settings, '/api/engines/2': view.engines[1] })
  renderAt('/settings', '/settings', <ToastProvider><Settings /></ToastProvider>)
  const rows = await screen.findAllByRole('button', { name: 'Edit' })
  fireEvent.click(rows[1])
  fireEvent.change(screen.getByRole('combobox', { name: /Round jump/ }), { target: { value: 'retime' } })
  await waitFor(() => {
    const patch = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(patch?.[0]).toBe('/api/engines/2')
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ seek_method: 'retime' })
  })
})

const lastPut = () => {
  const put = vi.mocked(fetch).mock.calls.filter(([url, init]) => url === '/api/settings' && init?.method === 'PUT').at(-1)
  return put && JSON.parse(String(put[1]?.body))
}

test('controls: keys shown as on the keyboard; a pressed key moves to the action, like in the game', async () => {
  mockApi({ '/api/engines': view, '/api/settings': settings })
  renderAt('/settings', '/settings', <ToastProvider><Settings /></ToastProvider>)
  const forward = await screen.findByRole('button', { name: 'Move forward: key' })
  expect(forward).toHaveTextContent('W')
  expect(screen.getByRole('button', { name: 'Move forward: alternate' })).toHaveTextContent('↑')
  expect(screen.getByRole('button', { name: 'Jump: key' })).toHaveTextContent('Space')
  const save = screen.getByRole('button', { name: 'Save keys' })
  expect(save).toBeDisabled()

  const jumpAlt = screen.getByRole('button', { name: 'Jump: alternate' })
  fireEvent.click(jumpAlt)
  expect(jumpAlt).toHaveTextContent('press a key or button…')
  fireEvent.mouseDown(jumpAlt, { button: 2 })
  expect(jumpAlt).toHaveTextContent('Right click')

  fireEvent.click(screen.getByRole('button', { name: 'Screenshot: key' }))
  fireEvent.keyDown(screen.getByRole('button', { name: 'Screenshot: key' }), { code: 'KeyW' }) // taken from Move forward
  expect(screen.getByRole('button', { name: 'Move forward: key' })).toHaveTextContent('—')

  fireEvent.click(screen.getByRole('button', { name: 'Move forward: alternate' }))
  fireEvent.keyDown(screen.getByRole('button', { name: 'Move forward: alternate' }), { code: 'Delete' }) // cleared
  fireEvent.click(save)
  await waitFor(() =>
    expect(lastPut()).toEqual({
      controls: { forward: [], jump: ['space', 'mouse2'], snapshot: ['w'] },
      binds: [{ key: 'f9', command: 'say gg' }],
    }),
  )
})

test('controls: own commands need a key; back to the defaults', async () => {
  mockApi({ '/api/engines': view, '/api/settings': settings })
  renderAt('/settings', '/settings', <ToastProvider><Settings /></ToastProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Add a command' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Own command 2' }), { target: { value: ' say hi ' } })
  const save = screen.getByRole('button', { name: 'Save keys' })
  expect(save).toBeDisabled()
  expect(screen.getByText(/needs a key/)).toBeInTheDocument()
  const key = screen.getByRole('button', { name: 'Own command 2: key' })
  fireEvent.click(key)
  fireEvent.keyDown(key, { code: 'NumpadAdd' })
  expect(key).toHaveTextContent('Num +')
  fireEvent.click(screen.getByRole('button', { name: 'Jump: key' }))
  fireEvent.keyDown(screen.getByRole('button', { name: 'Jump: key' }), { code: 'Delete' })
  fireEvent.click(screen.getByRole('button', { name: 'Back to the default keys' }))
  expect(screen.getByRole('button', { name: 'Jump: key' })).toHaveTextContent('Space')
  fireEvent.click(save)
  await waitFor(() =>
    expect(lastPut()).toEqual({
      controls: { forward: ['w', 'uparrow'], jump: ['space'], snapshot: ['f5'] },
      binds: [{ key: 'f9', command: 'say gg' }, { key: 'kp_plus', command: 'say hi' }],
    }),
  )
})

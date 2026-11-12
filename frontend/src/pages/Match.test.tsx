import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { ToastProvider } from '../components/Toasts'
import { detail, rounds } from '../fixtures'
import { mockApi, renderAt } from '../test-utils'
import Match from './Match'

afterEach(() => vi.unstubAllGlobals())

const played = { engine: 'CS15_P46_hl1110', engine_path: 'E:\\x', chosen: 'automatic', release: 'CS1.5', protocol: 46, seek: 21.8,
  seek_method: 'framerate', window: '1280x960 windowed', map_note: null, command: [] }

function bodies() {
  return vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'POST').map(([url, init]) => ({ url, body: JSON.parse(String(init?.body)), headers: init?.headers }))
}

test('shows line-ups and rounds; a round asks the app to play from 1 s before it', async () => {
  mockApi({ '/api/matches/7': detail, '/api/demos/': rounds, '/api/play': played })
  renderAt('/match/7', '/match/:id', <ToastProvider><Match /></ToastProvider>)
  expect(await screen.findByRole('heading', { name: 'aAa' })).toBeInTheDocument()
  expect(screen.getByText('STEAM_0:1:5')).toBeInTheDocument()
  expect(screen.getByText('also: Kwak')).toBeInTheDocument()
  expect(await screen.findByText('HS', { selector: '.hs' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'HellsGate' }).getAttribute('href')).toBe('/player/3')
  fireEvent.click(await screen.findByRole('button', { name: '▶ R2' }))
  await waitFor(() => expect(bodies()).toHaveLength(1))
  const call = bodies()[0]
  expect(call.url).toBe('/api/play')
  expect(call.body).toEqual({ sha1: 'a'.repeat(40), seek: 21.8 })
  expect(call.headers).toMatchObject({ 'X-Oldschool': '1' })
  expect(await screen.findByText(/Starting CS1.5 at 0:21/)).toBeInTheDocument()
})

test('round 1 and the Play button start from the beginning; a kill 5 s before it', async () => {
  mockApi({ '/api/matches/7': detail, '/api/demos/': rounds, '/api/play': played })
  renderAt('/match/7', '/match/:id', <ToastProvider><Match /></ToastProvider>)
  fireEvent.click(await screen.findByRole('button', { name: '▶ R1' }))
  fireEvent.click(screen.getByTitle(/before this kill/))
  await waitFor(() => expect(bodies()).toHaveLength(2))
  expect(bodies()[0].body.seek).toBeNull()
  expect(bodies()[1].body.seek).toBeCloseTo(8.81)
})

test('explains why a demo cannot be played', async () => {
  const noEngine = { ...detail, demos: [{ ...detail.demos[0], engine: null, play_problem: 'no working install for CS1.5 (network protocol 46): add one in Settings' }] }
  mockApi({ '/api/matches/7': noEngine, '/api/demos/': rounds })
  renderAt('/match/7', '/match/:id', <ToastProvider><Match /></ToastProvider>)
  expect(await screen.findByRole('button', { name: '▶ Play' })).toBeDisabled()
  expect(screen.getByText(/no working install for CS1.5/)).toBeInTheDocument()
})

test('says so when the match does not exist', async () => {
  mockApi({})
  renderAt('/match/99', '/match/:id', <Match />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Match not found.')
})

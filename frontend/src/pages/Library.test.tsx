import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { stats, summary } from '../fixtures'
import { mockApi, renderAt } from '../test-utils'
import Library from './Library'

afterEach(() => vi.unstubAllGlobals())

test('lists matches and filters by release', async () => {
  const calls = mockApi({ '/api/stats': stats, '/api/matches': { total: 1, page: 1, size: 50, items: [summary] } })
  renderAt('/', '/', <Library />)
  expect(await screen.findByText('1 match')).toBeInTheDocument()
  expect(screen.getByText(/Infinity-eSports/)).toBeInTheDocument()
  expect(screen.getByText('CT 5 : T 7 | CT 2 : T 10')).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('checkbox', { name: /CS1.3/ }))
  await waitFor(() => expect(calls.some((u) => u.includes('release=CS1.3'))).toBe(true))
})

test('player search is sent after a pause, with + and | kept', async () => {
  const calls = mockApi({ '/api/stats': stats, '/api/matches': { total: 0, page: 1, size: 50, items: [] } })
  renderAt('/', '/', <Library />)
  fireEvent.change(await screen.findByRole('searchbox', { name: 'Player(s)' }), { target: { value: 'kabal+ozie' } })
  await waitFor(() => expect(calls.some((u) => u.includes('player=kabal%2Bozie'))).toBe(true))
  expect(await screen.findByText('No match.')).toBeInTheDocument()
})

import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { mockApi, renderAt } from '../test-utils'
import Contact from './Contact'

afterEach(() => vi.unstubAllGlobals())

test('contact page: the author and his links, opened outside the app', async () => {
  mockApi({ '/api/health': { status: 'ok', version: '0.5.3', schema_version: 4 } })
  renderAt('/contact', '/contact', <Contact />)
  expect(screen.getByText('Guillaume <KabaL> ETTORI')).toBeInTheDocument()
  const links = Object.fromEntries(screen.getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')]))
  expect(links).toMatchObject({
    k4b4l74: 'https://github.com/k4b4l74',
    '@the_kabal': 'https://x.com/the_kabal',
    '@k4b4l74': 'https://www.youtube.com/@k4b4l74',
  })
  for (const a of screen.getAllByRole('link')) expect(a).toHaveAttribute('target', '_blank')
  expect(await screen.findByText(/Library Replayer v0\.5\.3/)).toBeInTheDocument()
})

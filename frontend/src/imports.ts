import type { Job } from './api/client'

export const baseName = (p: string) => p.split(/[\\/]/).filter(Boolean).pop() ?? p
export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '')
export const mb = (n: number) => (n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GB` : `${(n / 1024 ** 2).toFixed(1)} MB`)

export function jobTitle(j: Job): string {
  if (j.kind === 'reanalyse') return 'Re-analysis of the library'
  if (j.origin === 'folder') return `Folder ${j.paths[0] ?? ''}`
  if (j.origin === 'retry') return `Retry: ${baseName(j.paths[0] ?? '')}`
  const names = j.paths.map(baseName)
  return `Drop folder: ${names.slice(0, 3).join(', ')}${names.length > 3 ? ` and ${names.length - 3} more` : ''}`
}

export function countsText(j: Job): string {
  const c = j.counts
  if (j.kind === 'reanalyse') return [`${c.imported} files read again`, `${c.matches} matches`, c.failed && `${c.failed} failed`].filter(Boolean).join(' · ')
  return [
    `${c.imported} imported`,
    `${c.matches} new matches`,
    c.already && `${c.already} already in library`,
    c.no_demo && `${c.no_demo} without demo`,
    c.failed && `${c.failed} failed`,
  ]
    .filter(Boolean)
    .join(' · ')
}


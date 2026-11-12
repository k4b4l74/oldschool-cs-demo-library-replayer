import { createContext, useContext } from 'react'

export interface Upload {
  id: number
  name: string
  size: number
  sent: number
  state: 'waiting' | 'sending' | 'sent' | 'error'
  message?: string
}

export interface Uploads {
  items: Upload[]
  /** Send files to the Drop folder, one after the other. */
  add: (files: File[]) => void
  clear: () => void
  busy: boolean
}

export const UploadContext = createContext<Uploads>({ items: [], add: () => {}, clear: () => {}, busy: false })

export function useUploads(): Uploads {
  return useContext(UploadContext)
}

// Same list as the backend (archives.ARCHIVE_EXT + .dem).
const EXT = ['.dem', '.zip', '.rar', '.7z', '.ace', '.tar', '.tgz', '.tbz', '.tbz2', '.gz', '.bz2', '.xz', '.cab', '.lzh', '.arj', '.r00']

export function importable(name: string): boolean {
  const low = name.toLowerCase()
  return !low.startsWith('.') && EXT.some((e) => low.endsWith(e))
}

/** Files and folders dragged from Explorer. Folders cannot be read by a web page reliably. */
export function splitDropped(dt: DataTransfer): { files: File[]; folders: string[] } {
  const files: File[] = []
  const folders: string[] = []
  const items = Array.from(dt.items ?? [])
  if (items.length) {
    for (const item of items) {
      if (item.kind !== 'file') continue
      const entry = item.webkitGetAsEntry?.()
      const file = item.getAsFile()
      if (entry?.isDirectory) folders.push(entry.name)
      else if (file) files.push(file)
    }
  } else {
    files.push(...Array.from(dt.files))
  }
  return { files, folders }
}

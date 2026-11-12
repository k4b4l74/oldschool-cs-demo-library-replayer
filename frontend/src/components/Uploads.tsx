import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { uploadFile } from '../api/client'
import { useToast } from './toast-context'
import { importable, splitDropped, UploadContext, type Upload } from './upload-context'

let nextId = 1

/** Files sent from the page to the Drop folder; the backend imports them from there. */
export function UploadProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Upload[]>([])
  const queue = useRef<{ id: number; file: File }[]>([])
  const running = useRef(false)
  const qc = useQueryClient()

  const patch = (id: number, p: Partial<Upload>) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x)))

  const pump = useCallback(async () => {
    if (running.current) return
    running.current = true
    while (queue.current.length) {
      const { id, file } = queue.current.shift()!
      patch(id, { state: 'sending' })
      try {
        await uploadFile(file, (sent) => patch(id, { sent }))
        patch(id, { state: 'sent', sent: file.size })
        qc.invalidateQueries({ queryKey: ['imports'] })
      } catch (e) {
        patch(id, { state: 'error', message: (e as Error).message })
      }
    }
    running.current = false
  }, [qc])

  const add = useCallback(
    (files: File[]) => {
      const fresh: Upload[] = files.map((f) => {
        const ok = importable(f.name)
        const u: Upload = {
          id: nextId++,
          name: f.name,
          size: f.size,
          sent: 0,
          state: ok ? 'waiting' : 'error',
          message: ok ? undefined : 'not a demo (.dem) or an archive (.zip, .rar, .7z, .ace…)',
        }
        if (ok) queue.current.push({ id: u.id, file: f })
        return u
      })
      setItems((xs) => [...xs, ...fresh])
      void pump()
    },
    [pump],
  )

  const value = useMemo(
    () => ({
      items,
      add,
      clear: () => setItems((xs) => xs.filter((x) => x.state === 'waiting' || x.state === 'sending')),
      busy: items.some((x) => x.state === 'waiting' || x.state === 'sending'),
    }),
    [items, add],
  )
  return <UploadContext.Provider value={value}>{children}</UploadContext.Provider>
}

const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')

/** Drag files from Explorer anywhere on the app to import them. */
export function DropOverlay({ add }: { add: (files: File[]) => void }) {
  const [over, setOver] = useState(false)
  const depth = useRef(0)
  const toast = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    const enter = (e: DragEvent) => {
      if (!hasFiles(e)) return
      depth.current += 1
      setOver(true)
    }
    const leave = (e: DragEvent) => {
      if (!hasFiles(e)) return
      depth.current = Math.max(0, depth.current - 1)
      if (!depth.current) setOver(false)
    }
    const overFn = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault() // allows the drop
    }
    const drop = (e: DragEvent) => {
      if (!hasFiles(e) || !e.dataTransfer) return
      e.preventDefault()
      depth.current = 0
      setOver(false)
      const { files, folders } = splitDropped(e.dataTransfer)
      if (folders.length)
        toast('error', `Folders cannot be sent from the browser (${folders.join(', ')})`, 'Use “Import a folder” on the Import page, or copy the folder into the Drop folder.')
      if (files.length) {
        add(files)
        navigate('/import')
      }
    }
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragleave', leave)
    window.addEventListener('dragover', overFn)
    window.addEventListener('drop', drop)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('dragover', overFn)
      window.removeEventListener('drop', drop)
    }
  }, [add, navigate, toast])

  if (!over) return null
  return (
    <div className="drop-overlay" aria-hidden="true">
      <div>
        <span className="crosshair big" />
        Drop demos or archives to import them
      </div>
    </div>
  )
}

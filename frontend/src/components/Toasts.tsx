import { useCallback, useState } from 'react'
import { ToastContext, type ToastKind as Kind } from './toast-context'

interface Toast {
  id: number
  kind: Kind
  title: string
  detail?: string
}

let next = 1

/** Short messages in the corner, like the game's top-right notices. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = useCallback((kind: Kind, title: string, detail?: string) => {
    const id = next++
    setItems((xs) => [...xs.slice(-3), { id, kind, title, detail }])
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), kind === 'error' ? 9000 : 5000)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <b>{t.title}</b>
            {t.detail && <div>{t.detail}</div>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

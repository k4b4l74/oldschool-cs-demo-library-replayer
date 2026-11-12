import { createContext, useContext } from 'react'

export type ToastKind = 'info' | 'ok' | 'error'
export type PushToast = (kind: ToastKind, title: string, detail?: string) => void

export const ToastContext = createContext<PushToast>(() => {})

export function useToast(): PushToast {
  return useContext(ToastContext)
}

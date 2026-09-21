import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { NotificationsContext, type NotificationInput, type NotificationType } from './useNotifications'
import './notifications.css'

interface Notification extends NotificationInput {
  id: number
}

const DURATION_MS = 5000
const LABELS: Record<NotificationType, string> = {
  success: 'Éxito',
  error: 'Error',
  warning: 'Advertencia',
}
const SYMBOLS: Record<NotificationType, string> = {
  success: '✓',
  error: '!',
  warning: '⚠',
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Notification[]>([])
  const [target, setTarget] = useState<HTMLElement | null>(null)
  const nextId = useRef(0)
  const timers = useRef(new Map<number, number>())

  const dismiss = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id))
    timers.current.delete(id)
    setItems((current) => current.filter((item) => item.id !== id))
  }, [])

  const notify = useCallback((input: NotificationInput) => {
    const id = ++nextId.current
    setTarget(document.querySelector<HTMLElement>('dialog[open]') ?? document.body)
    setItems((current) => [...current, { ...input, id }])
    timers.current.set(id, window.setTimeout(() => dismiss(id), DURATION_MS))
  }, [dismiss])

  useEffect(() => {
    const moveToPage = () => setTarget(document.querySelector<HTMLElement>('dialog[open]') ?? document.body)
    const pendingTimers = timers.current
    document.addEventListener('close', moveToPage, true)
    return () => {
      document.removeEventListener('close', moveToPage, true)
      pendingTimers.forEach((timer) => window.clearTimeout(timer))
      pendingTimers.clear()
    }
  }, [])

  return (
    <NotificationsContext.Provider value={notify}>
      {children}
      {target && items.length > 0 && createPortal(
        <div className="notification-viewport">
          {items.map((item) => (
            <div
              key={item.id}
              className={`notification-toast notification-toast--${item.type}`}
              role={item.type === 'error' ? 'alert' : 'status'}
            >
              <span className="notification-symbol" aria-hidden="true">{SYMBOLS[item.type]}</span>
              <div className="notification-content">
                <strong>{LABELS[item.type]}</strong>
                <p>{item.message}</p>
              </div>
              <button
                className="notification-close"
                type="button"
                aria-label={`Cerrar notificación: ${LABELS[item.type]}`}
                onClick={() => dismiss(item.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>,
        target,
      )}
    </NotificationsContext.Provider>
  )
}

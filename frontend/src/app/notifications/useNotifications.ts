import { createContext, useContext } from 'react'

export type NotificationType = 'success' | 'error' | 'warning'

export interface NotificationInput {
  type: NotificationType
  message: string
}

export const NotificationsContext = createContext<((input: NotificationInput) => void) | null>(null)

export function useNotifications() {
  const notify = useContext(NotificationsContext)
  if (!notify) throw new Error('useNotifications requiere NotificationProvider')
  return notify
}

import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { queryClient } from './app/queryClient'
import { router } from './app/router'
import { NotificationProvider } from './app/notifications/Notifications'

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <RouterProvider router={router} />
      </NotificationProvider>
    </QueryClientProvider>
  )
}

export default App

import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { TourProvider } from './components/TourProvider'

import { queryClient } from './app/queryClient'
import { router } from './app/router'
import { NotificationProvider } from './app/notifications/Notifications'

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <TourProvider>
          <RouterProvider router={router} />
        </TourProvider>
      </NotificationProvider>
    </QueryClientProvider>
  )
}

export default App

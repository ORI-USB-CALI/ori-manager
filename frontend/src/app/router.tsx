import { createBrowserRouter } from 'react-router-dom'
import { AliadoDetailPage } from '../pages/AliadoDetailPage'
import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/aliados/:aliadoId',
    element: <AliadoDetailPage />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

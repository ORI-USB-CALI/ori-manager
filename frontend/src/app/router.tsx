import { createBrowserRouter } from 'react-router-dom'
import { AliadoDetallePage } from '../pages/AliadoDetallePage'
import { AliadoFormPage } from '../pages/AliadoFormPage'
import { AliadosPage } from '../pages/AliadosPage'
import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/aliados', element: <AliadosPage /> },
      { path: '/aliados/nuevo', element: <AliadoFormPage /> },
      { path: '/aliados/:aliadoId', element: <AliadoDetallePage /> },
      { path: '/aliados/:aliadoId/editar', element: <AliadoFormPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

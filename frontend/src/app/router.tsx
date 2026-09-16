import { createBrowserRouter } from 'react-router-dom'

import { UsuariosListPage } from '../features/usuarios/UsuariosListPage'
import { HomePage } from '../pages/HomePage'
import { NotFoundPage } from '../pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/usuarios',
    element: <UsuariosListPage />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

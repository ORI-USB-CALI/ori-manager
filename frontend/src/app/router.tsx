import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    element: <AppLayout />,
    children: [
      {
        path: '/',
        element: <HomePage />,
      },
      {
        element: <RequierePermiso permiso="usuarios.ver" />,
        children: [{ path: '/admin/usuarios', element: <UsuariosRolesPage /> }],
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])

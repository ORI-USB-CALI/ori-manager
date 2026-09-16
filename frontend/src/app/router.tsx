import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      {
        path: '/',
        element: <HomePage />,
      },
      {
        path: '/login',
        element: <LoginPage />,
      },
      {
        // Rutas privadas: envolver en RequierePermiso con el permiso que exige la sección.
        element: <RequierePermiso permiso="usuarios.gestionar" />,
        children: [{ path: '/admin/usuarios', element: <UsuariosRolesPage /> }],
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])

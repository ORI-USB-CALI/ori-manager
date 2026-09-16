import { createBrowserRouter } from 'react-router-dom'

import { UsuarioFormPage } from '../features/usuarios/UsuarioFormPage'
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
    path: '/usuarios/nuevo',
    element: <UsuarioFormPage />,
  },
  {
    path: '/usuarios/:id/editar',
    element: <UsuarioFormPage />,
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
])

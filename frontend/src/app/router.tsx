import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { AliadoDetallePage } from '../pages/AliadoDetallePage'
import { AliadosPage } from '../pages/AliadosPage'
import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { ConvenioNuevoPage } from '../pages/ConvenioNuevoPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { element: <RequierePermiso permiso="usuarios.ver" />, children: [{ path: '/admin/usuarios', element: <UsuariosRolesPage /> }] },
      { element: <RequierePermiso permiso="aliados.ver" />, children: [
        { path: '/aliados', element: <AliadosPage /> },
        { path: '/aliados/:aliadoId', element: <AliadoDetallePage /> },
      ] },
      { element: <RequierePermiso permiso="convenios.crear" />, children: [{ path: '/convenios/nuevo', element: <ConvenioNuevoPage /> }] },
      { element: <RequierePermiso permiso="convenios.ver" />, children: [{ path: '/convenios/:convenioId', element: <ConvenioDetallePage /> }] },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

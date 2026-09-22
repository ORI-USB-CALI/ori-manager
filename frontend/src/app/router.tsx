import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { AliadoDetallePage } from '../pages/AliadoDetallePage'
import { AliadosPage } from '../pages/AliadosPage'
import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { ConvenioNuevoPage } from '../pages/ConvenioNuevoPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { MisSolicitudesPage } from '../pages/MisSolicitudesPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RegistroPage } from '../pages/RegistroPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { SolicitudPage } from '../pages/SolicitudPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/registro', element: <RegistroPage /> },
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
      { element: <RequierePermiso permiso="solicitudes.ver_propias" />, children: [
        { path: '/solicitudes', element: <MisSolicitudesPage /> },
        { path: '/solicitudes/:solicitudId', element: <SolicitudPage /> },
      ] },
      { element: <RequierePermiso permiso="solicitudes.crear" />, children: [{ path: '/solicitudes/nueva', element: <SolicitudPage /> }] },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

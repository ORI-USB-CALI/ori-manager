import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { AliadoDetallePage } from '../pages/AliadoDetallePage'
import { AliadosPage } from '../pages/AliadosPage'
import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { ConvenioElaboracionPage } from '../pages/ConvenioElaboracionPage'
import { ConvenioHistorialPage } from '../pages/ConvenioHistorialPage'
import { ConvenioNuevoPage } from '../pages/ConvenioNuevoPage'
import { ConvenioRevisionFinalPage } from '../pages/ConvenioRevisionFinalPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { MisSolicitudesPage } from '../pages/MisSolicitudesPage'
import { RevisionesJuridicasPage } from '../pages/RevisionesJuridicasPage'
import { SolicitudRecibidaPage } from '../pages/SolicitudRecibidaPage'
import { SolicitudesRecibidasPage } from '../pages/SolicitudesRecibidasPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RegistroPage } from '../pages/RegistroPage'
import { RecuperarContrasenaPage } from '../pages/RecuperarContrasenaPage'
import { RestablecerContrasenaPage } from '../pages/RestablecerContrasenaPage'
import { VerificarCorreoPage } from '../pages/VerificarCorreoPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { SolicitudPage } from '../pages/SolicitudPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/registro', element: <RegistroPage /> },
  { path: '/recuperar-contrasena', element: <RecuperarContrasenaPage /> },
  { path: '/restablecer-contrasena', element: <RestablecerContrasenaPage /> },
  { path: '/verificar-correo', element: <VerificarCorreoPage /> },
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { element: <RequierePermiso permiso="usuarios.ver" />, children: [{ path: '/admin/usuarios', element: <UsuariosRolesPage /> }] },
      {
        element: <RequierePermiso permiso="aliados.ver" />, children: [
          { path: '/aliados', element: <AliadosPage /> },
          { path: '/aliados/:aliadoId', element: <AliadoDetallePage /> },
        ]
      },
      { element: <RequierePermiso permiso="convenios.crear" />, children: [{ path: '/convenios/nuevo', element: <ConvenioNuevoPage /> }] },
      {
        element: <RequierePermiso permiso="solicitudes.ver_recibidas" />, children: [
          { path: '/ori/solicitudes', element: <SolicitudesRecibidasPage /> },
          { path: '/ori/solicitudes/:solicitudId', element: <SolicitudRecibidaPage /> },
        ]
      },
      {
        element: <RequierePermiso permiso="convenios.ver" />, children: [
          { path: '/convenios/:convenioId', element: <ConvenioDetallePage /> },
          { path: '/convenios/:convenioId/elaboracion', element: <ConvenioElaboracionPage /> },
          { path: '/convenios/:convenioId/historial', element: <ConvenioHistorialPage /> },
          { path: '/convenios/:convenioId/revision-final', element: <ConvenioRevisionFinalPage /> },
        ]
      },
      {
        element: <RequierePermiso permiso="convenios.revisar" />, children: [
          { path: '/revisiones-juridicas', element: <RevisionesJuridicasPage /> },
        ]
      },
      {
        element: <RequierePermiso permiso="solicitudes.ver_propias" />, children: [
          { path: '/solicitudes', element: <MisSolicitudesPage /> },
          { path: '/solicitudes/:solicitudId', element: <SolicitudPage /> },
        ]
      },
      { element: <RequierePermiso permiso="solicitudes.crear" />, children: [{ path: '/solicitudes/nueva', element: <SolicitudPage /> }] },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

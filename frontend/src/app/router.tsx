import { createBrowserRouter } from 'react-router-dom'

import { RequierePermiso } from '../auth/RequierePermiso'
import { AliadoDetallePage } from '../pages/AliadoDetallePage'
import { AliadosPage } from '../pages/AliadosPage'
import { BitacoraPage } from '../pages/BitacoraPage'
import { ConsultaConveniosPage } from '../pages/ConsultaConveniosPage'
import { ConvenioDetallePage } from '../pages/ConvenioDetallePage'
import { ConvenioElaboracionPage } from '../pages/ConvenioElaboracionPage'
import { ConvenioHistorialPage } from '../pages/ConvenioHistorialPage'
import { ConvenioNuevoPage } from '../pages/ConvenioNuevoPage'
import { DocumentoAprobadoFirmaPage } from '../pages/DocumentoAprobadoFirmaPage'
import { FirmaConvenioPublicaPage } from '../pages/FirmaConvenioPublicaPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { MisSolicitudesPage } from '../pages/MisSolicitudesPage'
import { RevisionContrapartePage } from '../pages/RevisionContrapartePage'
import { RevisionContrapartePublicaPage } from '../pages/RevisionContrapartePublicaPage'
import { RevisionesContrapartePage } from '../pages/RevisionesContrapartePage'
import { RevisionesJuridicasPage } from '../pages/RevisionesJuridicasPage'
import { RenovacionesPage } from '../pages/RenovacionesPage'
import { ReporteConveniosActivosPage } from '../pages/ReporteConveniosActivosPage'
import { ReporteEstadisticasConveniosPage } from '../pages/ReporteEstadisticasConveniosPage'
import { SolicitudHistorialPage } from '../pages/SolicitudHistorialPage'
import { SolicitudRecibidaPage } from '../pages/SolicitudRecibidaPage'
import { SolicitudesRecibidasPage } from '../pages/SolicitudesRecibidasPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { RegistroPage } from '../pages/RegistroPage'
import { RecuperarContrasenaPage } from '../pages/RecuperarContrasenaPage'
import { RestablecerContrasenaPage } from '../pages/RestablecerContrasenaPage'
import { VerificarCorreoPage } from '../pages/VerificarCorreoPage'
import { UsuariosRolesPage } from '../pages/UsuariosRolesPage'
import { SolicitudPage } from '../pages/SolicitudPage'
import { TableroConveniosPage } from '../pages/TableroConveniosPage'
import { AppLayout } from './AppLayout'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/registro', element: <RegistroPage /> },
  { path: '/recuperar-contrasena', element: <RecuperarContrasenaPage /> },
  { path: '/restablecer-contrasena', element: <RestablecerContrasenaPage /> },
  { path: '/verificar-correo', element: <VerificarCorreoPage /> },
  { path: '/firma-convenio', element: <FirmaConvenioPublicaPage /> },
  { path: '/revision-contraparte', element: <RevisionContrapartePublicaPage /> },
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <HomePage /> },
      { element: <RequierePermiso permiso="convenios.gestionar_renovaciones" />, children: [
        { path: '/renovaciones', element: <RenovacionesPage />, handle: { layout: 'wide' } },
      ] },
      { element: <RequierePermiso permiso="convenios.ver_reportes" />, children: [
        { path: '/reportes/convenios-activos', element: <ReporteConveniosActivosPage />, handle: { layout: 'wide' } },
        { path: '/reportes/estadisticas-convenios', element: <ReporteEstadisticasConveniosPage />, handle: { layout: 'wide' } },
      ] },
      { element: <RequierePermiso permiso="usuarios.ver" />, children: [{ path: '/admin/usuarios', element: <UsuariosRolesPage /> }] },
      { element: <RequierePermiso permiso="auditoria.ver" />, children: [{ path: '/admin/bitacora', element: <BitacoraPage />, handle: { layout: 'wide' } }] },
      { element: <RequierePermiso permiso="aliados.ver" />, children: [
        { path: '/aliados', element: <AliadosPage /> },
        { path: '/aliados/:aliadoId', element: <AliadoDetallePage /> },
      ] },
      { element: <RequierePermiso permiso="convenios.crear" />, children: [{ path: '/convenios/nuevo', element: <ConvenioNuevoPage /> }] },
      { element: <RequierePermiso permiso="solicitudes.ver_recibidas" />, children: [
        { path: '/ori/solicitudes', element: <SolicitudesRecibidasPage />, handle: { layout: 'wide' } },
        { path: '/ori/solicitudes/:solicitudId', element: <SolicitudRecibidaPage /> },
        { path: '/ori/solicitudes/:solicitudId/historial', element: <SolicitudHistorialPage alcance="recibida" /> },
      ] },
      { element: <RequierePermiso permiso="convenios.ver" />, children: [
        { path: '/convenios', element: <ConsultaConveniosPage />, handle: { layout: 'wide' } },
        { path: '/convenios/tablero', element: <TableroConveniosPage />, handle: { layout: 'wide' } },
        { path: '/convenios/:convenioId', element: <ConvenioDetallePage /> },
        { path: '/convenios/:convenioId/elaboracion', element: <ConvenioElaboracionPage /> },
        { path: '/convenios/:convenioId/historial', element: <ConvenioHistorialPage /> },
      ] },
      { element: <RequierePermiso permiso="convenios.gestionar_firmas" />, children: [
        { path: '/convenios/:convenioId/firmas/documento-aprobado', element: <DocumentoAprobadoFirmaPage /> },
      ] },
      { element: <RequierePermiso permiso="convenios.revisar" />, children: [
        { path: '/revisiones-juridicas', element: <RevisionesJuridicasPage /> },
      ] },
      { element: <RequierePermiso permiso="convenios.revisar_contraparte_propia" />, children: [
        { path: '/revisiones-contraparte', element: <RevisionesContrapartePage /> },
        { path: '/revisiones-contraparte/:revisionId', element: <RevisionContrapartePage /> },
      ] },
      { element: <RequierePermiso permiso="solicitudes.ver_propias" />, children: [
        { path: '/solicitudes', element: <MisSolicitudesPage /> },
        { path: '/solicitudes/:solicitudId', element: <SolicitudPage /> },
        { path: '/solicitudes/:solicitudId/historial', element: <SolicitudHistorialPage alcance="propia" /> },
      ] },
      { element: <RequierePermiso permiso="solicitudes.crear" />, children: [{ path: '/solicitudes/nueva', element: <SolicitudPage /> }] },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

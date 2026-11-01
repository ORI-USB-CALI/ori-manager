import type { CodigoRol, Sesion } from '../auth/sesion'
import type { PasoRecorrido } from '../components/recorrido'

/** HU-38 FE-02. Se mantiene sincronizada con la versión enviada a /api/guias. */
export const VERSION_ONBOARDING = 1
export const CODIGO_ONBOARDING = 'ONBOARDING_INICIAL' as const

export const ROLES_SOLICITANTES: CodigoRol[] = [
  'SOLICITANTE_INTERNO',
  'SOLICITANTE_EXTERNO',
]

export function esSolicitante(rol: CodigoRol): boolean {
  return ROLES_SOLICITANTES.includes(rol)
}

/**
 * Contenido de la guía. Los nombres de `destino` se acuerdan con HU-38 FE-04;
 * el motor omite los destinos que aún no están presentes o están ocultos.
 * En cualquier ancho de pantalla quedan pasos de bienvenida/cierre centrados.
 */
export function pasosOnboardingInicial(sesion: Pick<Sesion, 'rol' | 'permisos'>): PasoRecorrido[] {
  if (!esSolicitante(sesion.rol.codigo)) return []

  const esInterno = sesion.rol.codigo === 'SOLICITANTE_INTERNO'
  const rol = sesion.rol.codigo

  return [
    {
      titulo: '¡Bienvenido a ORI Manager!',
      descripcion: esInterno
        ? 'Como solicitante interno, aquí puedes iniciar solicitudes de convenio y hacer seguimiento desde la Universidad.'
        : 'Como solicitante externo, aquí puedes proponer un convenio y consultar el estado de tus solicitudes.',
      roles: [rol],
    },
    {
      destino: 'inicio-accesos-rapidos',
      titulo: 'Tus accesos rápidos',
      descripcion: 'En esta sección encontrarás las opciones disponibles para tu cuenta.',
      roles: [rol],
    },
    {
      destino: 'inicio-nueva-solicitud',
      titulo: 'Inicia una solicitud',
      descripcion: 'Desde Nueva solicitud puedes diligenciar un convenio. Guarda tu borrador y radícalo cuando esté listo.',
      permiso: 'solicitudes.crear',
      roles: [rol],
    },
    {
      destino: 'inicio-mis-solicitudes',
      titulo: 'Consulta tus solicitudes',
      descripcion: 'En Mis solicitudes puedes revisar el estado, consultar observaciones y continuar las solicitudes editables.',
      permiso: 'solicitudes.ver_propias',
      roles: [rol],
    },
    {
      destino: 'navegacion-principal',
      titulo: 'Navegación',
      descripcion: 'Usa el menú para moverte entre las secciones. En celular puedes abrirlo desde el botón de menú.',
      roles: [rol],
    },
    {
      destino: 'centro-notificaciones',
      titulo: 'Notificaciones',
      descripcion: 'Aquí encontrarás avisos de actividades y novedades relacionadas con tus solicitudes.',
      roles: [rol],
    },
    {
      destino: 'ayuda-onboarding',
      titulo: 'Repite esta guía',
      descripcion: 'Puedes volver a abrir el recorrido cuando quieras desde el botón Ayuda.',
      roles: [rol],
    },
    {
      titulo: '¡Todo listo!',
      descripcion: 'El recorrido es informativo: no crea ni radica solicitudes. Puedes continuar a tu ritmo.',
      roles: [rol],
    },
  ]
}

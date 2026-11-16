import type { Permiso } from '../auth/sesion'
import type { SolicitudRecibida } from './solicitudes'

export function accionConvenioSolicitud(
  solicitud: Pick<SolicitudRecibida, 'id' | 'estado' | 'convenio_id' | 'convenio_etapa' | 'convenio_estado'>,
  puede: (permiso: Permiso) => boolean,
) {
  if (solicitud.estado !== 'APROBADA' || !puede('convenios.ver')) return null
  const to = `/convenios/${solicitud.convenio_id}`
  if (!solicitud.convenio_id) {
    return puede('solicitudes.gestionar_recibidas') && puede('convenios.editar')
      ? { to: `/ori/solicitudes/${solicitud.id}`, texto: 'Iniciar elaboración' } : null
  }
  if (solicitud.convenio_estado && solicitud.convenio_estado !== 'EN_TRAMITE') {
    return { to, texto: 'Ver convenio' }
  }
  switch (solicitud.convenio_etapa?.codigo) {
    case 'ELABORACION':
      return puede('convenios.editar')
        ? { to: `${to}/elaboracion`, texto: 'Continuar elaboración' }
        : { to, texto: 'Ver convenio' }
    case 'REVISION_AVAL_JURIDICO':
      return { to, texto: 'Consultar revisión' }
    case 'REVISION_CONTRAPARTE':
      return { to, texto: puede('convenios.gestionar_revision_contraparte') ? 'Continuar trámite' : 'Ver convenio' }
    case 'REVISION_FINAL':
      return { to, texto: puede('convenios.gestionar_firmas') ? 'Continuar trámite' : 'Ver convenio' }
    case 'APROBACION_FIRMAS':
    case 'FIRMA_ARCHIVO_SEGUIMIENTO':
      return { to, texto: puede('convenios.gestionar_firmas') ? 'Gestionar firmas' : 'Ver convenio' }
    default:
      return { to, texto: 'Ver convenio' }
  }
}

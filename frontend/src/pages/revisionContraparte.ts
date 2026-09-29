import { apiFetch } from '../app/api'

export interface RevisionContrapartePendiente {
  revision_id: number
  convenio_id: number
  codigo_convenio: string | null
  objeto: string | null
  version_numero: number
  fecha_envio: string
  enviada_por: { id: number; nombre_completo: string; correo: string }
}

export const CLAVE_REVISIONES_CONTRAPARTE = ['revisiones-contraparte', 'pendientes'] as const

export function obtenerRevisionesContraparte() {
  return apiFetch<RevisionContrapartePendiente[]>('/convenios/revisiones-contraparte/pendientes')
}

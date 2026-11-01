import { apiFetch } from '../app/api'
import type { CodigoGuia } from '../components/recorrido'

export type EstadoGuia = 'PENDIENTE' | 'COMPLETADO' | 'OMITIDO'
export type EstadoFinalGuia = Exclude<EstadoGuia, 'PENDIENTE'>

export interface GuiaUsuario {
  guia: CodigoGuia
  estado: EstadoGuia
  version: number | null
  actualizado_en: string | null
}

/** Consulta la guía del usuario autenticado. Nunca se envía un ID de usuario. */
export function consultarGuia(guia: CodigoGuia): Promise<GuiaUsuario> {
  return apiFetch<GuiaUsuario>(`/guias/${guia}`)
}

/** El backend conserva COMPLETADO como estado irreversible. */
export function actualizarGuia(guia: CodigoGuia, estado: EstadoFinalGuia, version: number): Promise<GuiaUsuario> {
  return apiFetch<GuiaUsuario>(`/guias/${guia}`, {
    method: 'PUT',
    body: JSON.stringify({ estado, version }),
  })
}

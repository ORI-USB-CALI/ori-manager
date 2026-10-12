import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../app/api'
import type { EstadoConvenio, UsuarioResumen } from './epica02'

export interface EvaluacionConvenio {
  id: number
  convenio_id: number
  fue_funcional: boolean
  calificacion: number
  observaciones: string
  evaluado_por_id: number
  evaluado_por: UsuarioResumen
  creado_en: string
}

/**
 * Estado de la evaluación tal como lo expone el backend.
 *
 * `evaluable` es la regla de elegibilidad ya resuelta en el servidor: la
 * interfaz no debe comparar contra un estado concreto, así sigue funcionando
 * cuando se amplíen los estados evaluables.
 */
export interface EstadoEvaluacion {
  evaluable: boolean
  estado_convenio: EstadoConvenio
  evaluacion: EvaluacionConvenio | null
}

export interface EvaluacionConvenioCrear {
  fue_funcional: boolean
  calificacion: number
  observaciones: string
}

/** RN-08: 1 es cumplimiento muy bajo, 10 cumplimiento total. */
export const LEYENDA_CALIFICACION = '1 = cumplimiento muy bajo, 10 = cumplimiento total'
export const CALIFICACION_MINIMA = 1
export const CALIFICACION_MAXIMA = 10
export const OPCIONES_CALIFICACION = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const
export const LIMITE_OBSERVACIONES = 4000

export function claveEvaluacion(convenioId: number) {
  return ['convenio', convenioId, 'evaluacion'] as const
}

export function obtenerEstadoEvaluacion(convenioId: number, signal?: AbortSignal) {
  return apiFetch<EstadoEvaluacion>(`/convenios/${convenioId}/evaluacion`, { signal })
}

export function useEvaluacionConvenio(convenioId: number, habilitada: boolean) {
  return useQuery({
    queryKey: claveEvaluacion(convenioId),
    queryFn: ({ signal }) => obtenerEstadoEvaluacion(convenioId, signal),
    enabled: habilitada && Number.isInteger(convenioId) && convenioId > 0,
    retry: false,
  })
}

export function registrarEvaluacion(convenioId: number, datos: EvaluacionConvenioCrear) {
  return apiFetch<EvaluacionConvenio>(`/convenios/${convenioId}/evaluacion`, {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

/**
 * Deja pasar el motivo textual del backend solo si parece un mensaje de
 * negocio: así CA-02 llega al usuario sin exponer trazas, SQL ni URLs.
 */
function detalleSeguro(error: ApiError): string | null {
  const detalle = typeof error.detail === 'string' ? error.detail.trim() : ''
  if (
    error.status >= 400 && error.status < 500
    && detalle.length > 0 && detalle.length <= 500
    && /\p{L}/u.test(detalle)
    && Array.from(detalle).every((caracter) => caracter.charCodeAt(0) > 31 && caracter.charCodeAt(0) !== 127)
    && !/[<>[\]{}]/u.test(detalle)
    && !/traceback|stack\s*trace|\bat\s+\S+\s*\(|\b(select|insert|update|delete)\b.+\b(from|into|set)\b|\b\w*(?:error|exception)\s*:|https?:\/\/|\.(?:py|tsx?|jsx?):\d+/i.test(detalle)
  ) return detalle
  return null
}

export function mensajeErrorEvaluacion(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión ha expirado. Inicia sesión nuevamente.'
    if (error.status === 403) return 'No tienes permiso para gestionar la evaluación de este convenio.'
    const detalle = detalleSeguro(error)
    if (detalle) return detalle
    if (error.status === 404) return 'El convenio ya no está disponible. Actualiza la página.'
    if (error.status === 409) {
      return 'No se pudo registrar la evaluación: el convenio puede no admitir evaluación todavía o ya tener una registrada. Consulta su situación actual.'
    }
    if (error.status === 422) {
      return 'Revisa los datos de la evaluación: la calificación debe estar entre 1 y 10 y los comentarios son obligatorios.'
    }
    return 'No se pudo completar la acción. Comprueba tu conexión y vuelve a intentarlo.'
  }
  if (error instanceof Error && error.message.trim()) return error.message
  return 'No se pudo completar la acción. Comprueba tu conexión y vuelve a intentarlo.'
}

/** Normaliza los errores de validación de Pydantic a un mapa campo → mensaje. */
export function erroresEvaluacion(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object') return {}
  if (Array.isArray(error.detail)) {
    return Object.fromEntries(error.detail.flatMap((item: unknown) => {
      if (!item || typeof item !== 'object' || !('loc' in item) || !('msg' in item)) return []
      const loc = Array.isArray(item.loc) ? item.loc : []
      const campo = loc.at(-1)
      if (typeof campo !== 'string' || typeof item.msg !== 'string') return []
      return [[campo, item.msg.replace(/^Value error, /, '')]]
    }))
  }
  if (!('errors' in error.detail)) return {}
  const errores = error.detail.errors
  return errores && typeof errores === 'object' ? errores as Record<string, string> : {}
}

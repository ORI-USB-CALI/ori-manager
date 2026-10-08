import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../app/api'
import type { EstadoConvenio } from './epica02'

export type EstadoSeguimientoRenovacion =
  | 'PENDIENTE_DE_DECISION'
  | 'RENOVACION_INICIADA'
  | 'NO_SE_RENOVARA'

export interface SeguimientoRenovacion {
  convenio_id: number
  codigo: string | null
  objeto: string | null
  aliado: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  estado_convenio: EstadoConvenio
  estado_seguimiento: EstadoSeguimientoRenovacion
  tipo_convenio: string | null
  convenio_renovacion_id: number | null
  codigo_renovacion: string | null
  numero_renovacion: number | null
  etapa_renovacion: string | null
}

export interface RenovacionIniciada {
  convenio_origen_id: number
  convenio_renovacion_id: number
  codigo: string | null
  numero_renovacion: number
  estado: EstadoConvenio
  etapa: string
}

export interface DecisionNoRenovacion {
  convenio_id: number
  fecha_vencimiento_origen: string
  decidida_por_id: number
  decidida_en: string
  estado_seguimiento: 'NO_SE_RENOVARA'
}

export const CLAVE_RENOVACIONES = ['convenios', 'renovaciones'] as const

export function useSeguimientoRenovaciones(habilitada: boolean) {
  return useQuery({
    queryKey: CLAVE_RENOVACIONES,
    queryFn: ({ signal }) => apiFetch<SeguimientoRenovacion[]>('/convenios/renovaciones', { signal }),
    enabled: habilitada,
    retry: false,
    refetchOnMount: 'always',
  })
}

export function iniciarRenovacion(convenioId: number) {
  return apiFetch<RenovacionIniciada>(`/convenios/${convenioId}/renovaciones`, { method: 'POST' })
}

export function registrarNoRenovacion(convenioId: number) {
  return apiFetch<DecisionNoRenovacion>(`/convenios/${convenioId}/no-renovar`, { method: 'POST' })
}

export function mensajeErrorAccion(error: Error, tipo: 'iniciar' | 'no-renovar'): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión ha expirado. Inicia sesión nuevamente.'
    if (error.status === 403) return 'No tienes permiso para gestionar renovaciones.'
    const detalle = typeof error.detail === 'string' ? error.detail.trim() : ''
    if (
      error.status >= 400 && error.status < 500
      && detalle.length > 0 && detalle.length <= 500
      && /\p{L}/u.test(detalle)
      && Array.from(detalle).every((caracter) => caracter.charCodeAt(0) > 31 && caracter.charCodeAt(0) !== 127)
      && !/[<>[\]{}]/u.test(detalle)
      && !/traceback|stack\s*trace|\bat\s+\S+\s*\(|\b(select|insert|update|delete)\b.+\b(from|into|set)\b|\b\w*(?:error|exception)\s*:|https?:\/\/|\.(?:py|tsx?|jsx?):\d+/i.test(detalle)
    ) return detalle
    if (error.status === 409) {
      return tipo === 'iniciar'
        ? 'No se pudo iniciar la renovación. El convenio puede tener una renovación en curso o ya no admitir un nuevo intento. Consulta su situación actual.'
        : 'El convenio ya no está pendiente de decisión: puede tener una renovación en curso, una decisión registrada o estar fuera del periodo permitido.'
    }
    if (error.status === 404) return 'El convenio ya no está disponible. Actualiza el panel.'
  }
  return 'No se pudo completar la acción. Comprueba tu conexión y vuelve a intentarlo.'
}

export function formatearFechaConvenio(fecha: string | null): string {
  if (!fecha) return 'Sin fecha registrada'
  return new Date(`${fecha}T00:00:00Z`).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

export function diasRestantes(fecha: string | null): string | null {
  if (!fecha) return null
  const hoy = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const parte = (tipo: Intl.DateTimeFormatPartTypes) => hoy.find((item) => item.type === tipo)?.value
  const fechaHoy = `${parte('year')}-${parte('month')}-${parte('day')}`
  const dias = Math.round((Date.parse(`${fecha}T00:00:00Z`) - Date.parse(`${fechaHoy}T00:00:00Z`)) / 86_400_000)
  if (dias === 0) return 'Vence hoy'
  if (dias < 0) return `Venció hace ${-dias} ${dias === -1 ? 'día' : 'días'}`
  return `${dias} ${dias === 1 ? 'día restante' : 'días restantes'}`
}

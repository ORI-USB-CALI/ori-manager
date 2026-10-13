import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { EstadoConvenio, TipoAliado } from './epica02'

export interface FiltrosEstadisticasConvenios {
  estado?: EstadoConvenio
  aliado_activo?: boolean
  tipo_aliado?: TipoAliado
  pais?: string
}

export interface Conteo {
  etiqueta: string
  cantidad: number
}

export interface ReporteEstadisticoConvenios {
  datos_suficientes: boolean
  total_convenios: number
  por_estado_contractual: Conteo[]
  por_vigencia_activa: Conteo[]
  por_estado_aliado: Conteo[]
  por_tipo_aliado: Conteo[]
  por_pais: Conteo[]
}

export const CLAVE_REPORTE_ESTADISTICAS_CONVENIOS = ['convenios', 'reportes', 'estadisticas'] as const

function construirQueryString(filtros: FiltrosEstadisticasConvenios): string {
  const params = new URLSearchParams()
  if (filtros.estado) params.set('estado', filtros.estado)
  if (filtros.aliado_activo !== undefined) params.set('aliado_activo', String(filtros.aliado_activo))
  if (filtros.tipo_aliado) params.set('tipo_aliado', filtros.tipo_aliado)
  if (filtros.pais) params.set('pais', filtros.pais)
  const query = params.toString()
  return query ? `?${query}` : ''
}

export function obtenerReporteEstadisticasConvenios(filtros: FiltrosEstadisticasConvenios) {
  return apiFetch<ReporteEstadisticoConvenios>(
    `/convenios/reportes/estadisticas${construirQueryString(filtros)}`,
  )
}

export function useReporteEstadisticasConvenios(
  filtros: FiltrosEstadisticasConvenios,
  habilitada: boolean,
) {
  return useQuery({
    queryKey: [...CLAVE_REPORTE_ESTADISTICAS_CONVENIOS, filtros],
    queryFn: () => obtenerReporteEstadisticasConvenios(filtros),
    enabled: habilitada,
    retry: false,
  })
}

// Descargas directas: el navegador navega con la cookie de sesión existente
// y el backend responde con Content-Disposition: attachment.
export function urlDescargaEstadisticasConvenios(
  formato: 'pdf' | 'excel',
  filtros: FiltrosEstadisticasConvenios,
): string {
  return `/api/convenios/reportes/estadisticas/${formato}${construirQueryString(filtros)}`
}

import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { EstadoConvenio, TipoAliado } from './epica02'

export interface EtapaConsultaResumen {
  codigo: string
  nombre: string
}

export interface TipoConvenioConsultaResumen {
  id: number
  nombre: string
}

export interface ProgramaConsultaResumen {
  id: number
  nombre: string
}

export interface ContraparteConsulta {
  nombre: string | null
  tipo: TipoAliado | null
  identificacion: string | null
  es_aliado_formal: boolean
}

export interface ConvenioConsulta {
  id: number
  codigo: string | null
  objeto: string | null
  estado: EstadoConvenio
  etapa: EtapaConsultaResumen | null
  tipo_convenio: TipoConvenioConsultaResumen | null
  contraparte: ContraparteConsulta
  programa: ProgramaConsultaResumen | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  fecha_formalizacion: string | null
}

export interface ConvenioConsultaListado {
  items: ConvenioConsulta[]
  total: number
}

export interface FiltrosConsultaConvenio {
  buscar?: string
  limite: number
  desplazamiento: number
}

export function construirQuery(filtros: FiltrosConsultaConvenio): string {
  const parametros = new URLSearchParams()
  if (filtros.buscar?.trim()) parametros.set('buscar', filtros.buscar.trim())
  if (filtros.limite) parametros.set('limite', String(filtros.limite))
  if (filtros.desplazamiento) parametros.set('desplazamiento', String(filtros.desplazamiento))
  return parametros.toString()
}

export function useConsultaConvenios(filtros: FiltrosConsultaConvenio) {
  return useQuery({
    queryKey: ['convenios', 'consulta', filtros],
    queryFn: () => apiFetch<ConvenioConsultaListado>(`/convenios?${construirQuery(filtros)}`),
    placeholderData: keepPreviousData,
  })
}

export function formatearFecha(fecha: string | null): string {
  if (!fecha) return 'Sin fecha'
  return new Date(`${fecha}T00:00:00Z`).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

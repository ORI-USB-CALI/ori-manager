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

// HU-27: no se persiste en el backend (vive junto a FiltrosConsultaConvenio,
// no en models/enums.py), así que tampoco se modela como un enum compartido
// aquí: es un espejo literal de TipoFiltroFecha.
export type TipoFiltroFecha = 'FORMALIZACION' | 'VIGENCIA'

export interface FiltrosConsultaConvenio {
  buscar?: string
  limite: number
  desplazamiento: number
  tipo_fecha?: TipoFiltroFecha
  fecha_desde?: string
  fecha_hasta?: string
  estados?: EstadoConvenio[]
  tipos_contraparte?: TipoAliado[]
  programa_id?: number
}

export function construirQuery(filtros: FiltrosConsultaConvenio): string {
  const parametros = new URLSearchParams()
  if (filtros.buscar?.trim()) parametros.set('buscar', filtros.buscar.trim())
  if (filtros.limite) parametros.set('limite', String(filtros.limite))
  if (filtros.desplazamiento) parametros.set('desplazamiento', String(filtros.desplazamiento))
  // HU-27 FE-3: fecha_desde/fecha_hasta solo viajan junto con tipo_fecha,
  // igual que exige el backend (BE-1): si no hay ninguna fecha, tipo_fecha
  // tampoco se envía, para no forzar un filtro vacío.
  if (filtros.tipo_fecha && (filtros.fecha_desde || filtros.fecha_hasta)) {
    parametros.set('tipo_fecha', filtros.tipo_fecha)
    if (filtros.fecha_desde) parametros.set('fecha_desde', filtros.fecha_desde)
    if (filtros.fecha_hasta) parametros.set('fecha_hasta', filtros.fecha_hasta)
  }
  // HU-28: estado y tipo_contraparte son listas repetibles (?estado=A&estado=B).
  filtros.estados?.forEach((estado) => parametros.append('estado', estado))
  filtros.tipos_contraparte?.forEach((tipo) => parametros.append('tipo_contraparte', tipo))
  if (filtros.programa_id) parametros.set('programa_id', String(filtros.programa_id))
  return parametros.toString()
}

export function useConsultaConvenios(filtros: FiltrosConsultaConvenio) {
  return useQuery({
    queryKey: ['convenios', 'consulta', filtros],
    queryFn: () => apiFetch<ConvenioConsultaListado>(`/convenios?${construirQuery(filtros)}`),
    placeholderData: keepPreviousData,
  })
}

// HU-28 BE-1: catálogo de opciones para los filtros avanzados (espejo de
// UnidadOrganizacionalResumen en schemas/convenio.py).
export interface ProgramaCatalogo {
  id: number
  codigo: string
  nombre: string
  tipo: string
}

export interface CatalogosConsulta {
  estados: EstadoConvenio[]
  tipos_contraparte: TipoAliado[]
  programas: ProgramaCatalogo[]
}

const DIEZ_MINUTOS_MS = 10 * 60 * 1000

export function useCatalogosConsulta() {
  return useQuery({
    queryKey: ['convenios', 'catalogos', 'consulta'],
    queryFn: () => apiFetch<CatalogosConsulta>('/convenios/catalogos/consulta'),
    // HU-28 FE-1: el catálogo casi no cambia, no hace falta revalidarlo en
    // cada render de la página.
    staleTime: DIEZ_MINUTOS_MS,
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

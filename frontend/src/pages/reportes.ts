import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'

export interface ActividadResumen {
  id: number
  titulo: string
  estado: string
  fecha_planificada: string | null
  fecha_ejecucion: string | null
}

export interface ConvenioReporteActivo {
  id: number
  codigo: string | null
  objeto: string | null
  estado: string
  aliado: string | null
  tipo_convenio: string | null
  unidad_organizacional: string | null
  responsable: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  actividades: ActividadResumen[]
}

export const CLAVE_REPORTE_CONVENIOS_ACTIVOS = ['convenios', 'reportes', 'activos'] as const

export function obtenerReporteConveniosActivos() {
  return apiFetch<ConvenioReporteActivo[]>('/convenios/reportes/activos')
}

export function useReporteConveniosActivos(habilitada: boolean) {
  return useQuery({
    queryKey: CLAVE_REPORTE_CONVENIOS_ACTIVOS,
    queryFn: obtenerReporteConveniosActivos,
    enabled: habilitada,
    retry: false,
  })
}

// Descargas directas: el navegador navega con la cookie de sesión
// existente y el backend responde con Content-Disposition: attachment.
export const URL_DESCARGA_REPORTE_PDF = '/api/convenios/reportes/activos/pdf'
export const URL_DESCARGA_REPORTE_EXCEL = '/api/convenios/reportes/activos/excel'

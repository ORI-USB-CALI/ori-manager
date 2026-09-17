import { apiFetch } from './http'

export type AlcanceConvenio = 'PROGRAMA' | 'INSTITUCIONAL'

/**
 * Datos que la interfaz de "registro base" (HU-06) recolecta hoy.
 *
 * El backend acepta mas campos (tipo_convenio_id, etapa_actual_id,
 * fechas de vencimiento/firma, renovaciones, etc.), pero esos
 * pertenecen a etapas posteriores del ciclo de vida del convenio
 * (elaboracion, firmas, renovacion) y no al registro base de HU-06.
 */
export interface ConvenioCreateInput {
  solicitud_id: number
  aliado_id?: number | null
  creado_por_id: number
  objeto?: string | null
  alcance?: AlcanceConvenio | null
}

export interface ConvenioRead {
  id: number
  codigo: string | null
  solicitud_id: number
  aliado_id: number | null
  tipo_convenio_id: number | null
  etapa_actual_id: number | null
  estado: string
  objeto: string | null
  alcance: string | null
  unidad_organizacional_id: number | null
  implicacion_financiera: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  fecha_firma: string | null
  duracion_meses: number | null
  porcentaje_avance: number | null
  convenio_origen_id: number | null
  numero_renovacion: number | null
  creado_por_id: number
  creado_en: string
  actualizado_en: string
}

export function createConvenio(input: ConvenioCreateInput): Promise<ConvenioRead> {
  return apiFetch<ConvenioRead>('/convenios', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function getConvenio(id: number): Promise<ConvenioRead> {
  return apiFetch<ConvenioRead>(`/convenios/${id}`)
}

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { EstadoConvenio } from './epica02'

export interface ActividadUtilizacion {
  id: number
  convenio_id: number
  estado: 'REALIZADA'
  fecha_ejecucion: string
  titulo: string
  descripcion: string
  responsable_nombre: string | null
  observaciones: string | null
  registrado_por_id: number
  creado_en: string
}

export interface ActividadUtilizacionCrear {
  fecha_ejecucion: string
  titulo: string
  descripcion: string
  responsable_nombre: string
  observaciones: string | null
}

export const ESTADOS_REGISTRO_UTILIZACION: readonly EstadoConvenio[] = ['VIGENTE', 'POR_VENCER']

export function claveActividadesUtilizacion(convenioId: number) {
  return ['convenio', convenioId, 'actividades-utilizacion'] as const
}

export function useActividadesUtilizacion(convenioId: number) {
  return useQuery({
    queryKey: claveActividadesUtilizacion(convenioId),
    queryFn: ({ signal }) => apiFetch<ActividadUtilizacion[]>(
      `/convenios/${convenioId}/actividades-utilizacion`,
      { signal },
    ),
    retry: false,
  })
}

export function registrarActividadUtilizacion(convenioId: number, datos: ActividadUtilizacionCrear) {
  return apiFetch<ActividadUtilizacion>(`/convenios/${convenioId}/actividades-utilizacion`, {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

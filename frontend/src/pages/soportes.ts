import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'

export interface SoporteConvenio {
  id: number
  nombre_original: string
  tamano_bytes: number
  fecha_creacion: string
  usuario_nombre: string | null
}

export function claveSoportesConvenio(convenioId: number) {
  return ['convenios', convenioId, 'documentos'] as const
}

/**
 * Estados del convenio que admiten adjuntar soportes (CA-04 de HU-22C).
 * Un convenio activo para soportes es aquel que está en vigor: VIGENTE o POR_VENCER.
 */
export function esConvenioActivoParaSoportes(estado: string | null | undefined): boolean {
  return estado === 'VIGENTE' || estado === 'POR_VENCER'
}

export function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatearFechaSoporte(valor: string): string {
  return new Date(valor).toLocaleString()
}

export function obtenerSoportesConvenio(convenioId: number, signal?: AbortSignal) {
  return apiFetch<SoporteConvenio[]>(`/convenios/${convenioId}/documentos`, { signal })
}

export function useSoportesConvenio(convenioId: number, habilitada: boolean) {
  return useQuery({
    queryKey: claveSoportesConvenio(convenioId),
    queryFn: ({ signal }) => obtenerSoportesConvenio(convenioId, signal),
    enabled: habilitada && Number.isInteger(convenioId) && convenioId > 0,
    retry: false,
  })
}

// Estado de las guías del usuario actual (API de HU-38 BE-02).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { CodigoGuia } from '../components/recorrido'

export type EstadoGuia = 'PENDIENTE' | 'COMPLETADO' | 'OMITIDO'

export interface EstadoGuiaUsuario {
  guia: CodigoGuia
  estado: EstadoGuia
  version: number | null
  actualizado_en: string | null
}

/** Versión del contenido de las guías. Se guarda como información; no reabre guías finalizadas. */
export const VERSION_GUIAS = 1

export const claveGuia = (guia: CodigoGuia) => ['guias', guia] as const

export function useEstadoGuia(guia: CodigoGuia, habilitada = true) {
  return useQuery({
    queryKey: claveGuia(guia),
    enabled: habilitada,
    queryFn: () => apiFetch<EstadoGuiaUsuario>(`/guias/${guia}`),
    retry: false,
  })
}

export function useRegistrarEstadoGuia(guia: CodigoGuia) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (estado: Exclude<EstadoGuia, 'PENDIENTE'>) =>
      apiFetch<EstadoGuiaUsuario>(`/guias/${guia}`, {
        method: 'PUT',
        body: JSON.stringify({ estado, version: VERSION_GUIAS }),
      }),
    onSuccess: (estado) => queryClient.setQueryData(claveGuia(guia), estado),
  })
}

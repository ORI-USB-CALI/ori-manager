import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'

export type RangoVencimiento = '0_30' | '31_60' | '61_90' | '91_120'

export interface AlertaVencimiento {
  convenio_id: number
  codigo: string | null
  objeto: string | null
  fecha_vencimiento: string
  dias_restantes: number
  rango_vencimiento: RangoVencimiento
}

export const CLAVE_ALERTAS_VENCIMIENTO = ['convenios', 'alertas-vencimiento'] as const

export function obtenerAlertasVencimiento() {
  return apiFetch<AlertaVencimiento[]>('/convenios/alertas-vencimiento')
}

export function useAlertasVencimiento(habilitada: boolean) {
  return useQuery({
    queryKey: CLAVE_ALERTAS_VENCIMIENTO,
    queryFn: obtenerAlertasVencimiento,
    enabled: habilitada,
    retry: false,
    refetchOnMount: 'always',
  })
}

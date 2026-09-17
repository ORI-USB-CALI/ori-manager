import { useQuery } from '@tanstack/react-query'
import { fetchAliadoDetalle } from '../services/aliadosApi'

export function useAliadoDetalle(aliadoId: string | undefined) {
  return useQuery({
    queryKey: ['aliado', aliadoId],
    queryFn: () => {
      if (!aliadoId) {
        throw new Error('ID de aliado no proporcionado')
      }
      return fetchAliadoDetalle(aliadoId)
    },
    enabled: Boolean(aliadoId),
    retry: false,
  })
}

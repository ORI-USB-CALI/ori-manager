import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { AliadoCrear, AliadoEditar, FiltrosAliado } from './types'

const CLAVE = ['aliados'] as const

export function useAliados(filtros: FiltrosAliado) {
  return useQuery({
    queryKey: [...CLAVE, 'lista', filtros],
    queryFn: () => api.listarAliados(filtros),
    placeholderData: keepPreviousData,
  })
}

export function useAliado(aliadoId: number | undefined) {
  return useQuery({
    queryKey: [...CLAVE, aliadoId],
    queryFn: () => api.consultarAliado(aliadoId as number),
    enabled: aliadoId !== undefined,
    retry: false,
  })
}

export function useConveniosDeAliado(aliadoId: number | undefined) {
  return useQuery({
    queryKey: [...CLAVE, aliadoId, 'convenios'],
    queryFn: () => api.listarConveniosDeAliado(aliadoId as number),
    enabled: aliadoId !== undefined,
    retry: false,
  })
}

// Cualquier escritura invalida todo lo de aliados: listado, ficha y convenios.
function useInvalidarAliados() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: CLAVE })
}

export function useCrearAliado() {
  const invalidar = useInvalidarAliados()
  return useMutation({
    mutationFn: (datos: AliadoCrear) => api.crearAliado(datos),
    onSuccess: invalidar,
  })
}

export function useEditarAliado(aliadoId: number) {
  const invalidar = useInvalidarAliados()
  return useMutation({
    mutationFn: (datos: AliadoEditar) => api.editarAliado(aliadoId, datos),
    onSuccess: invalidar,
  })
}

export function useCambiarEstadoAliado(aliadoId: number) {
  const invalidar = useInvalidarAliados()
  return useMutation({
    mutationFn: (accion: 'inactivar' | 'reactivar') =>
      accion === 'inactivar' ? api.inactivarAliado(aliadoId) : api.reactivarAliado(aliadoId),
    onSuccess: invalidar,
  })
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as usuariosApi from './api'
import type { UsuarioActualizar, UsuarioCambiarRol, UsuarioCrear } from './types'

const CLAVE_USUARIOS = ['usuarios'] as const

export function useUsuarios() {
  return useQuery({
    queryKey: CLAVE_USUARIOS,
    queryFn: usuariosApi.listarUsuarios,
  })
}

export function useUsuario(id: number | undefined) {
  return useQuery({
    queryKey: [...CLAVE_USUARIOS, id],
    queryFn: () => usuariosApi.obtenerUsuario(id as number),
    enabled: id !== undefined,
  })
}

export function useCrearUsuario() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (datos: UsuarioCrear) => usuariosApi.crearUsuario(datos),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  })
}

export function useEditarUsuario(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (datos: UsuarioActualizar) => usuariosApi.editarUsuario(id, datos),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  })
}

export function useCambiarRolUsuario(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (datos: UsuarioCambiarRol) => usuariosApi.cambiarRolUsuario(id, datos),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  })
}

export function useDesactivarUsuario() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => usuariosApi.desactivarUsuario(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS }),
  })
}

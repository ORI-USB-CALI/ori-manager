import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../app/api'

export type CodigoRol =
  | 'ADMINISTRADOR_ORI'
  | 'GESTOR_ORI'
  | 'REVISOR_ORI'
  | 'SOLICITANTE_INTERNO'
  | 'SOLICITANTE_EXTERNO'

export type TipoUsuario = 'INTERNO' | 'EXTERNO'

export type Permiso =
  | 'usuarios.ver'
  | 'usuarios.crear'
  | 'usuarios.editar'
  | 'usuarios.cambiar_rol'
  | 'usuarios.cambiar_estado'
  | 'aliados.ver'
  | 'aliados.editar'
  | 'aliados.cambiar_estado'
  | 'convenios.ver'
  | 'convenios.crear'
  | 'convenios.editar'

export interface RolSesion {
  codigo: CodigoRol
  nombre: string
}

export interface Sesion {
  id: number
  correo: string
  nombre_completo: string
  activo: boolean
  tipo_usuario: TipoUsuario
  rol: RolSesion
  permisos: Permiso[]
}

export const ETIQUETAS_ROL: Record<CodigoRol, string> = {
  ADMINISTRADOR_ORI: 'Administrador ORI',
  GESTOR_ORI: 'Gestor ORI',
  REVISOR_ORI: 'Revisor ORI',
  SOLICITANTE_INTERNO: 'Solicitante interno',
  SOLICITANTE_EXTERNO: 'Solicitante externo',
}

export const CLAVE_SESION = ['sesion'] as const

export async function obtenerSesion(): Promise<Sesion | null> {
  try {
    return await apiFetch<Sesion>('/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useSesion() {
  const consulta = useQuery({
    queryKey: CLAVE_SESION,
    queryFn: obtenerSesion,
    retry: false,
  })
  const sesion = consulta.data ?? null

  return {
    sesion,
    cargando: consulta.isPending,
    error: consulta.error,
    puede: (permiso: Permiso) => sesion?.permisos.includes(permiso) ?? false,
  }
}

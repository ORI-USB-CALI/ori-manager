import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../app/api'

// Espejo de backend/src/backend/core/permisos.py. La matriz rol→permisos vive solo en el backend.
export type Rol = 'administrador' | 'usuario_ori'

export type Permiso =
  | 'usuarios.gestionar'
  | 'aliados.ver'
  | 'aliados.gestionar'
  | 'convenios.ver'
  | 'convenios.gestionar'

export const ETIQUETAS_ROL: Record<Rol, string> = {
  administrador: 'Administrador',
  usuario_ori: 'Usuario ORI',
}

export interface Sesion {
  id: string
  email: string
  is_active: boolean
  rol: Rol
  permisos: Permiso[]
}

export const CLAVE_SESION = ['sesion'] as const

// Sin sesión (401) = Invitado: `sesion` es null.
async function obtenerSesion(): Promise<Sesion | null> {
  try {
    return await apiFetch<Sesion>('/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useSesion() {
  const { data, isPending } = useQuery({
    queryKey: CLAVE_SESION,
    queryFn: obtenerSesion,
    retry: false,
  })
  const sesion = data ?? null

  return {
    sesion,
    cargando: isPending,
    // Solo controla visibilidad; la autorización real la hace el backend.
    puede: (permiso: Permiso) => sesion?.permisos.includes(permiso) ?? false,
  }
}

// Tipos calcados de backend/src/backend/schemas/usuario.py en la rama
// feature/HU03-CRUD-de-usuarios. `id` viene expuesto en UsuarioListar y
// UsuarioLeer desde el commit 4d39c6e (Jesús Gelves).

export type CodigoRol = 'ADMINISTRADOR_ORI' | 'GESTOR_ORI' | 'REVISOR_ORI'

export interface RolLeer {
  codigo: CodigoRol
  nombre: string
}

export interface UsuarioCrear {
  correo: string
  contrasena: string
  nombre_completo: string
  rol: CodigoRol
  documento_identidad?: string | null
  telefono?: string | null
  cargo?: string | null
}

export interface UsuarioActualizar {
  nombre_completo?: string
  documento_identidad?: string | null
  telefono?: string | null
  cargo?: string | null
}

export interface UsuarioCambiarRol {
  rol: CodigoRol
}

export interface UsuarioLeer {
  id: number
  correo: string
  nombre_completo: string
  documento_identidad: string | null
  telefono: string | null
  cargo: string | null
  rol: RolLeer
  activo: boolean
  ultimo_acceso: string | null
}

export interface UsuarioListar {
  id: number
  correo: string
  nombre_completo: string
  rol: RolLeer
  activo: boolean
}

// RN-04 / CA-05: el formulario de usuarios internos solo permite estos 3 roles.
export const ROLES_INTERNOS: RolLeer[] = [
  { codigo: 'ADMINISTRADOR_ORI', nombre: 'Administrador ORI' },
  { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' },
  { codigo: 'REVISOR_ORI', nombre: 'Revisor ORI' },
]

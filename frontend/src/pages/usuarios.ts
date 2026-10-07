import {
  ETIQUETAS_ROL,
  type CodigoRol,
  type TipoUsuario,
} from '../auth/sesion'

export interface Usuario {
  id: number
  correo: string
  nombre_completo: string
  documento_identidad: string | null
  telefono: string | null
  cargo: string | null
  tipo_usuario: TipoUsuario
  entidad_externa: string | null
  activo: boolean
  ultimo_acceso: string | null
  rol: {
    codigo: CodigoRol
    nombre: string
  }
  unidad_organizacional_id: number | null
}

export const CLAVE_USUARIOS = ['usuarios'] as const

const ROLES_SOLICITANTES: readonly CodigoRol[] = [
  'SOLICITANTE_INTERNO',
  'SOLICITANTE_EXTERNO',
]

export const ROLES_POR_TIPO: Record<TipoUsuario, readonly CodigoRol[]> = {
  INTERNO: ['ADMINISTRADOR_ORI', 'GESTOR_ORI', 'REVISOR_ORI'],
  EXTERNO: [],
}

export function opcionesRol(tipo: TipoUsuario) {
  return ROLES_POR_TIPO[tipo].map((codigo) => ({
    value: codigo,
    label: ETIQUETAS_ROL[codigo],
  }))
}

export function etiquetaTipo(tipo: TipoUsuario): string {
  return tipo === 'INTERNO' ? 'Interno' : 'Externo'
}

export function esRolSolicitante(codigo: CodigoRol): boolean {
  return ROLES_SOLICITANTES.includes(codigo)
}

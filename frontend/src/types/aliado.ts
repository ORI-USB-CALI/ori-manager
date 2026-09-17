export type EstadoAliado = 'ACTIVO' | 'INACTIVO'

export type EstadoConvenio =
  | 'VIGENTE'
  | 'EN_TRAMITE'
  | 'FINALIZADO'
  | 'VENCIDO'
  | 'CANCELADO'

export interface Convenio {
  id: string
  codigo: string
  titulo: string
  tipo_convenio?: string | null
  estado: EstadoConvenio
  fecha_inicio?: string | null
  fecha_fin?: string | null
  creado_en: string
}

export interface AliadoDetalle {
  id: string
  nombre: string
  nit_o_identificacion?: string | null
  tipo_aliado?: string | null
  estado: EstadoAliado
  descripcion?: string | null
  creado_en: string
  convenios: Convenio[]
}

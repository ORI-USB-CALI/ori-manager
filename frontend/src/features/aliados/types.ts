// Espejo de backend/src/backend/api/schemas/aliado.py y convenio.py,
// con los enums de backend/src/backend/models/enums.py.

export type TipoAliado = 'universidad' | 'colegio' | 'empresa' | 'entidad_gubernamental'

export type EstadoAliado = 'activo' | 'inactivo'

export type EstadoConvenio =
  | 'en_tramite'
  | 'vigente'
  | 'por_vencer'
  | 'vencido'
  | 'renovado'
  | 'finalizado'
  | 'cancelado'

export type RolUsuario =
  | 'administrador_ori'
  | 'gestor_ori'
  | 'revisor_ori'
  | 'solicitante_interno'

export interface AliadoLeer {
  id: number
  identificacion: string
  nombre: string
  tipo: TipoAliado
  sector_economico: string | null
  pais_id: number | null
  ciudad: string | null
  direccion: string | null
  telefono: string | null
  correo: string | null
  sitio_web: string | null
  estado: EstadoAliado
  creado_en: string
  actualizado_en: string
}

export interface AliadoCrear {
  identificacion: string
  nombre: string
  tipo: TipoAliado
  sector_economico?: string | null
  ciudad?: string | null
  direccion?: string | null
  telefono?: string | null
  correo?: string | null
  sitio_web?: string | null
}

export type AliadoEditar = Partial<Omit<AliadoCrear, 'identificacion'>>

export interface AliadoListado {
  items: AliadoLeer[]
  total: number
}

export interface FiltrosAliado {
  buscar?: string
  tipo?: TipoAliado
  estado?: EstadoAliado
  limite: number
  desplazamiento: number
}

export interface ConvenioDeAliado {
  id: number
  aliado_id: number | null
  estado: EstadoConvenio
  creado_en: string
  actualizado_en: string
}

export const TIPO_ALIADO_ETIQUETA: Record<TipoAliado, string> = {
  universidad: 'Universidad',
  colegio: 'Colegio',
  empresa: 'Empresa',
  entidad_gubernamental: 'Entidad gubernamental',
}

export const ESTADO_CONVENIO_ETIQUETA: Record<EstadoConvenio, string> = {
  en_tramite: 'En trámite',
  vigente: 'Vigente',
  por_vencer: 'Por vencer',
  vencido: 'Vencido',
  renovado: 'Renovado',
  finalizado: 'Finalizado',
  cancelado: 'Cancelado',
}

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'

export type TipoAliado = 'UNIVERSIDAD' | 'COLEGIO' | 'EMPRESA' | 'ENTIDAD_GUBERNAMENTAL'
export type TipoIdentificacion = 'NIT' | 'CEDULA_CIUDADANIA' | 'CEDULA_EXTRANJERIA' | 'PASAPORTE' | 'IDENTIFICACION_FISCAL_EXTRANJERA' | 'OTRO'
export const TIPOS_IDENTIFICACION: TipoIdentificacion[] = ['NIT', 'CEDULA_CIUDADANIA', 'CEDULA_EXTRANJERIA', 'PASAPORTE', 'IDENTIFICACION_FISCAL_EXTRANJERA', 'OTRO']
export type EstadoConvenio =
  | 'EN_TRAMITE'
  | 'VIGENTE'
  | 'POR_VENCER'
  | 'VENCIDO'
  | 'RENOVADO'
  | 'FINALIZADO'
  | 'CANCELADO'

export interface ConvenioResumen {
  id: number
  codigo: string | null
  estado: EstadoConvenio
  objeto: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  fecha_firma: string | null
  tipo_convenio_id: number | null
  tipo_convenio: { id: number; codigo: string; nombre: string } | null
}

export interface Aliado {
  id: number
  nombre: string
  tipo: TipoAliado
  sector_economico: string | null
  identificacion: string
  tipo_identificacion: TipoIdentificacion
  pais_id: number | null
  ciudad: string | null
  direccion: string | null
  telefono: string | null
  correo: string | null
  sitio_web: string | null
  activo: boolean
  creado_en: string
  actualizado_en: string
}

export interface AliadoPerfil extends Aliado {
  convenios: ConvenioResumen[]
}

export interface Convenio {
  id: number
  codigo: string | null
  solicitud_id: number
  aliado_id: number | null
  aliado: Pick<Aliado, 'id' | 'nombre' | 'identificacion' | 'activo'> | null
  tipo_convenio_id: number | null
  etapa_actual_id: number | null
  estado: EstadoConvenio
  objeto: string | null
  alcance: 'PROGRAMA' | 'INSTITUCIONAL' | null
  unidad_organizacional_id: number | null
  implicacion_financiera: string | null
  fecha_inicio: string | null
  fecha_vencimiento: string | null
  fecha_firma: string | null
  duracion_meses: number | null
  porcentaje_avance: number | null
  convenio_origen_id: number | null
  numero_renovacion: number | null
  creado_por_id: number
  creado_por: { id: number; nombre_completo: string; correo: string }
  creado_en: string
  actualizado_en: string
}

export const ETIQUETA_TIPO: Record<TipoAliado, string> = {
  UNIVERSIDAD: 'Universidad',
  COLEGIO: 'Colegio',
  EMPRESA: 'Empresa',
  ENTIDAD_GUBERNAMENTAL: 'Entidad gubernamental',
}

export function useAliados(soloActivos = false) {
  return useQuery({
    queryKey: ['aliados', { soloActivos }],
    queryFn: () =>
      apiFetch<{ items: Aliado[]; total: number }>(
        `/aliados?limite=100${soloActivos ? '&activo=true' : ''}`,
      ),
    retry: false,
  })
}

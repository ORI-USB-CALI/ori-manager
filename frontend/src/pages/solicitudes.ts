import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { TipoUsuario } from '../auth/sesion'
import type { TipoAliado, TipoIdentificacion } from './epica02'

export type EstadoSolicitud = 'BORRADOR' | 'RADICADA' | 'EN_ESTUDIO' | 'DEVUELTA' | 'APROBADA' | 'RECHAZADA'
export type TipoDocumento = 'CAMARA_COMERCIO' | 'RUT' | 'CEDULA_REPRESENTANTE_LEGAL' | 'OTRO_DOCUMENTO_REPRESENTACION' | 'OTRO_SOPORTE'

export interface DocumentoSolicitud {
  id: number
  tipo_documento: TipoDocumento
  nombre_original: string
  tipo_mime: string
  tamano_bytes: number
  creado_en: string
}

export interface Solicitud {
  id: number
  consecutivo: string
  tipo_solicitante: TipoUsuario
  solicitante_id: number
  unidad_organizacional_id: number | null
  solicitante_nombre: string | null
  solicitante_correo: string | null
  solicitante_documento: string | null
  solicitante_cargo: string | null
  solicitante_entidad: string | null
  solicitante_unidad: string | null
  solicitante_programa: string | null
  nombre_aliado_propuesto: string | null
  tipo_identificacion_aliado_propuesto: TipoIdentificacion | null
  identificacion_aliado_propuesto: string | null
  tipo_aliado_propuesto: TipoAliado | null
  correo_aliado_propuesto: string | null
  pais_aliado_propuesto: string | null
  ciudad_aliado_propuesto: string | null
  telefono_aliado_propuesto: string | null
  direccion_aliado_propuesto: string | null
  sector_economico_aliado_propuesto: string | null
  contacto_contraparte_nombre: string | null
  contacto_contraparte_cargo: string | null
  contacto_contraparte_telefono: string | null
  contacto_contraparte_correo: string | null
  tipo_convenio_id: number | null
  justificacion: string | null
  objeto: string | null
  actividades_por_parte: string | null
  metas_esperadas: string | null
  implicacion_financiera: string | null
  vigencia_estimada: string | null
  requisitos_renovacion: string | null
  supervisor_usb_nombre: string | null
  supervisor_usb_cargo: string | null
  supervisor_usb_telefono: string | null
  supervisor_usb_correo: string | null
  supervisor_contraparte_nombre: string | null
  supervisor_contraparte_cargo: string | null
  supervisor_contraparte_telefono: string | null
  supervisor_contraparte_correo: string | null
  observaciones: string | null
  estado: EstadoSolicitud
  fecha_radicacion: string | null
  fecha_recibido_ori: string | null
  documentos: DocumentoSolicitud[]
  creado_en: string
  actualizado_en: string
}

export interface SolicitudRecibida extends Solicitud {
  convenio_id: number | null
  tipo_convenio_nombre: string | null
}

export interface CatalogosSolicitud {
  solicitante: {
    tipo_usuario: TipoUsuario
    tipo_unidad: 'FACULTAD' | 'PROGRAMA' | 'UNIDAD_ADMINISTRATIVA' | null
    nombre: string
    correo: string
    identificacion: string | null
    entidad: string | null
    cargo: string | null
    unidad: string | null
    programa: string | null
  }
  tipos_convenio: Array<{ id: number; codigo: string; nombre: string; naturaleza: string | null }>
  tipos_documento: Array<{ codigo: TipoDocumento; nombre: string; es_representacion_legal: boolean }>
  requiere_documento_representacion: boolean
}

export function useCatalogosSolicitud() {
  return useQuery({ queryKey: ['solicitudes', 'catalogos'], queryFn: () => apiFetch<CatalogosSolicitud>('/solicitudes/catalogos'), retry: false })
}

export function useSolicitud(id: number | null) {
  return useQuery({
    queryKey: ['solicitudes', id],
    queryFn: () => apiFetch<Solicitud>(`/solicitudes/${id}`),
    enabled: id !== null,
    retry: false,
  })
}

export function useSolicitudRecibida(id: number | null) {
  return useQuery({
    queryKey: ['solicitudes', 'recibidas', id],
    queryFn: () => apiFetch<SolicitudRecibida>(`/solicitudes/recibidas/${id}`),
    enabled: id !== null,
    retry: false,
  })
}

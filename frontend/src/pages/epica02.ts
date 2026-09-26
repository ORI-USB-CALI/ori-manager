import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { EstadoSolicitud } from './solicitudes'

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

export interface SolicitudAntecedente {
  id: number
  consecutivo: string
  tipo_solicitante: 'INTERNO' | 'EXTERNO'
  estado: EstadoSolicitud
  objeto: string | null
  justificacion: string | null
  actividades_por_parte: string | null
  metas_esperadas: string | null
  implicacion_financiera: string | null
  vigencia_estimada: string | null
  requisitos_renovacion: string | null
  observaciones: string | null
  fecha_radicacion: string | null

  solicitante_nombre: string | null
  solicitante_correo: string | null
  solicitante_cargo: string | null
  solicitante_unidad: string | null
  solicitante_programa: string | null
  solicitante_entidad: string | null

  nombre_aliado_propuesto: string | null
  identificacion_aliado_propuesto: string | null
  tipo_aliado_propuesto: string | null
  correo_aliado_propuesto: string | null
  pais_aliado_propuesto: string | null
  ciudad_aliado_propuesto: string | null

  contacto_contraparte_nombre: string | null
  contacto_contraparte_cargo: string | null
  contacto_contraparte_telefono: string | null
  contacto_contraparte_correo: string | null

  supervisor_usb_nombre: string | null
  supervisor_usb_cargo: string | null
  supervisor_usb_telefono: string | null
  supervisor_usb_correo: string | null
  supervisor_contraparte_nombre: string | null
  supervisor_contraparte_cargo: string | null
  supervisor_contraparte_telefono: string | null
  supervisor_contraparte_correo: string | null
}

export interface EtapaResumen {
  id: number
  orden: number
  codigo: string
  nombre: string
}

export interface TipoConvenioResumen {
  id: number
  codigo: string
  nombre: string
  naturaleza: string | null
}

export interface TipoConvenioElaboracionOpcion extends TipoConvenioResumen {
  duracion_meses_defecto: number | null
}

export interface UnidadOrganizacionalResumen {
  id: number
  codigo: string
  nombre: string
  tipo: string
}

export interface ElaboracionConvenio extends Convenio {
  solicitud: SolicitudAntecedente
  etapa_actual: EtapaResumen | null
  tipo_convenio: TipoConvenioResumen | null
  unidad_organizacional: UnidadOrganizacionalResumen | null
}

export function useElaboracionConvenio(convenioId: number) {
  return useQuery({
    queryKey: ['convenios', convenioId, 'elaboracion'],
    queryFn: () => apiFetch<ElaboracionConvenio>(`/convenios/${convenioId}/elaboracion`),
    enabled: Number.isInteger(convenioId),
    retry: false,
  })
}

export interface CampoFaltante {
  campo: string
  motivo: string
}

export interface ValidacionElaboracion {
  completo: boolean
  faltantes: CampoFaltante[]
}

export function useValidacionElaboracion(convenioId: number) {
  return useQuery({
    queryKey: ['convenios', convenioId, 'elaboracion', 'validacion'],
    queryFn: () => apiFetch<ValidacionElaboracion>(`/convenios/${convenioId}/elaboracion/validacion`),
    enabled: Number.isInteger(convenioId),
    retry: false,
  })
}

export interface UnidadOrganizacional {
  id: number
  codigo: string
  nombre: string
  tipo: 'FACULTAD' | 'PROGRAMA' | 'UNIDAD_ADMINISTRATIVA'
}

export interface CatalogosElaboracion {
  tipos_convenio: TipoConvenioElaboracionOpcion[]
  unidades_organizacionales: UnidadOrganizacional[]
}

export function useCatalogosElaboracion() {
  return useQuery({
    queryKey: ['convenios', 'catalogos', 'elaboracion'],
    queryFn: () => apiFetch<CatalogosElaboracion>('/convenios/catalogos/elaboracion'),
    retry: false,
  })
}

export interface FirmaConvenio {
  id: number
  convenio_id: number
  orden: number
  rol_firmante: string
  parte: string
  usuario_id: number | null
  nombre_firmante: string | null
  cargo_firmante: string | null
  modalidad: string | null
  estado: string
  fecha_firma: string | null
  documento_id: number | null
  observacion: string | null
  creado_en: string
}

export interface DocumentoRevisionResumen {
  id: number
  nombre_archivo: string
  tipo_documento: string
  ruta_almacenamiento: string
  tamano_bytes: number
  creado_en: string
}

export interface ConvenioRevisionFinal {
  id: number
  codigo: string | null
  solicitud_id: number
  aliado_id: number | null
  objeto: string | null
  implicacion_financiera: string | null
  estado: EstadoConvenio
  etapa_actual_id: number | null
  revision_final_aprobada: boolean
  proceso_firmas_abierto: boolean
  documento_aprobado: DocumentoRevisionResumen | null
  firmas: FirmaConvenio[]
  creado_en: string
  actualizado_en: string
}

export function useRevisionFinalConvenio(convenioId: number) {
  return useQuery({
    queryKey: ['convenios', convenioId, 'revision-final'],
    queryFn: () => apiFetch<ConvenioRevisionFinal>(`/convenios/${convenioId}/revision-final`),
    enabled: Number.isInteger(convenioId),
    retry: false,
  })
}


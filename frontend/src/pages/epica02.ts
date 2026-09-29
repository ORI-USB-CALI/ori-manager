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
  plantilla_origen_id: number | null
  version_actual: number
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

export interface EtapaTablero extends EtapaResumen {
  area_responsable: string | null
}

export interface ConvenioTablero {
  id: number
  codigo: string | null
  estado: EstadoConvenio
  etapa_actual: EtapaTablero | null
  aliado: { id: number; nombre: string } | null
  aliado_propuesto: string | null
  responsable: UsuarioResumen | null
  puede_ver_detalle: boolean
}

export interface TableroConvenios {
  etapas: EtapaTablero[]
  convenios: ConvenioTablero[]
}

export function useTableroConvenios() {
  return useQuery({
    queryKey: ['convenios', 'tablero'],
    queryFn: () => apiFetch<TableroConvenios>('/convenios/tablero'),
    retry: false,
  })
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
  plantilla_origen: PlantillaConvenioResumen | null
  contenido: Record<string, unknown> | null
}

export interface PlantillaConvenioResumen {
  id: number
  codigo: string
  nombre: string
}

export interface VersionConvenioResumen {
  id: number
  numero: number
  autor: { id: number; nombre_completo: string; correo: string }
  etapa: EtapaResumen
  contexto: string
  creado_en: string
  plantilla: PlantillaConvenioResumen | null
}

export interface UsuarioResumen {
  id: number
  nombre_completo: string
  correo: string
}

export interface ObservacionRevision {
  id: number
  origen: 'REVISOR_ORI' | 'CONTRAPARTE'
  descripcion: string
  respuesta: string | null
  estado: 'PENDIENTE' | 'ATENDIDA'
  registrada_por: UsuarioResumen | null
  responsable: UsuarioResumen | null
  atendida_por: UsuarioResumen | null
  fecha_atencion: string | null
  creado_en: string
}

export interface InvitacionContraparteTrazabilidad {
  id: number
  generada_por: UsuarioResumen
  correo_destino: string
  correo_cc: string | null
  expira_en: string
  enviado_en: string | null
  utilizado_en: string | null
  revocado_en: string | null
  creado_en: string
}

export interface RespuestaContraparteTrazabilidad {
  nombre_firmante: string
  cargo_firmante: string
  correo_actor: string
  firma_sha256: string | null
  creado_en: string
  tiene_firma: boolean
}

export interface RevisionConvenioTrazabilidad {
  id: number
  version_convenio_id: number | null
  version_resultado_id: number | null
  version_convenio: { id: number; numero: number } | null
  version_resultado: { id: number; numero: number } | null
  instancia_juridica: number | null
  numero_ronda: number | null
  tipo: 'JURIDICA' | 'CONTRAPARTE' | 'FINAL'
  estado: 'PENDIENTE' | 'RESUELTA'
  resultado: 'APROBADA' | 'DEVUELTA' | null
  responsable: UsuarioResumen | null
  creada_por: UsuarioResumen | null
  resuelta_por: UsuarioResumen | null
  snapshot_datos: { objeto?: string | null } | null
  creado_en: string
  resuelta_en: string | null
  observaciones: ObservacionRevision[]
  invitaciones_contraparte: InvitacionContraparteTrazabilidad[]
  respuesta_contraparte: RespuestaContraparteTrazabilidad | null
}

export interface HistorialConvenio {
  revisiones: RevisionConvenioTrazabilidad[]
  cambios_etapa: Array<{
    id: number
    etapa_origen: EtapaResumen | null
    etapa_destino: EtapaResumen
    usuario: UsuarioResumen
    responsable: UsuarioResumen | null
    observacion: string | null
    fecha_cambio: string
  }>
}

export function useVersionesConvenio(convenioId: number) {
  return useQuery({
    queryKey: ['convenios', convenioId, 'versiones'],
    queryFn: () => apiFetch<VersionConvenioResumen[]>(`/convenios/${convenioId}/versiones`),
    enabled: Number.isInteger(convenioId),
    retry: false,
  })
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

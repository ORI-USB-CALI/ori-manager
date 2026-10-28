import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiFetch } from '../app/api'
import type { CodigoRol } from '../auth/sesion'
import type { UsuarioResumen } from './epica02'

export type AccionBitacora = 'INSERT' | 'UPDATE' | 'DELETE'
export type EjecucionBitacora = 'HUMANA' | 'AUTOMATICA'

export interface RegistroBitacora {
  id: number
  fecha_hora: string
  // HT-09, CA-03: nulo únicamente en procesos automáticos sin usuario
  // originador; no se inventa un usuario ficticio para representarlos.
  usuario: UsuarioResumen | null
  rol: string | null
  entidad: string
  registro_id: number
  accion: AccionBitacora
  campo: string | null
  valor_anterior: string | null
  valor_nuevo: string | null
  contexto: string | null
  // HT-09: nulos en los registros previos a HT-09 y en los cambios que no
  // declaran una acción de negocio estructurada.
  evento: string | null
  etapa: string | null
  version: number | null
  ejecucion: EjecucionBitacora | null
  responsable: UsuarioResumen | null
}

export const ETIQUETAS_EJECUCION: Record<EjecucionBitacora, string> = {
  HUMANA: 'Humana',
  AUTOMATICA: 'Automática',
}

export interface PaginaBitacora {
  items: RegistroBitacora[]
  total: number
}

export interface FiltrosBitacora {
  desde: string
  hasta: string
  entidad: string
  rol: CodigoRol | ''
  accion: AccionBitacora | ''
  registro_id: string
  usuario_id: string
  orden: 'asc' | 'desc'
}

export const ETIQUETAS_ACCION: Record<AccionBitacora, string> = {
  INSERT: 'Creación',
  UPDATE: 'Modificación',
  DELETE: 'Eliminación',
}

export const TAMANO_PAGINA_BITACORA = 25
export const LONGITUD_MAXIMA_ENTIDAD = 80

// Los días del formulario son días calendario de Bogotá (UTC-05:00, sin horario de verano).
const DESFASE_BOGOTA = '-05:00'

export const FILTROS_BITACORA_VACIOS: FiltrosBitacora = {
  desde: '',
  hasta: '',
  entidad: '',
  rol: '',
  accion: '',
  registro_id: '',
  usuario_id: '',
  orden: 'desc',
}

export function hayFiltrosBitacora(filtros: FiltrosBitacora): boolean {
  return (Object.keys(FILTROS_BITACORA_VACIOS) as (keyof FiltrosBitacora)[])
    .some((clave) => filtros[clave] !== FILTROS_BITACORA_VACIOS[clave])
}

export function rangoFechasInvalido({ desde, hasta }: FiltrosBitacora): boolean {
  // Las fechas llegan como AAAA-MM-DD, así que se comparan como texto.
  return Boolean(desde && hasta && desde > hasta)
}

export function consultaBitacora(filtros: FiltrosBitacora, pagina: number): string {
  const parametros = new URLSearchParams()
  const entidad = filtros.entidad.trim()
  if (filtros.desde) parametros.set('desde', `${filtros.desde}T00:00:00${DESFASE_BOGOTA}`)
  if (filtros.hasta) parametros.set('hasta', `${filtros.hasta}T23:59:59.999${DESFASE_BOGOTA}`)
  if (entidad) parametros.set('entidad', entidad)
  if (filtros.rol) parametros.set('rol', filtros.rol)
  if (filtros.accion) parametros.set('accion', filtros.accion)
  if (filtros.registro_id.trim()) parametros.set('registro_id', filtros.registro_id.trim())
  if (filtros.usuario_id.trim()) parametros.set('usuario_id', filtros.usuario_id.trim())
  parametros.set('orden', filtros.orden)
  parametros.set('limite', String(TAMANO_PAGINA_BITACORA))
  parametros.set('desplazamiento', String((pagina - 1) * TAMANO_PAGINA_BITACORA))
  return parametros.toString()
}

export function useBitacora(filtros: FiltrosBitacora, pagina: number, habilitada: boolean) {
  const consulta = consultaBitacora(filtros, pagina)
  return useQuery({
    queryKey: ['auditoria', consulta],
    queryFn: ({ signal }) => apiFetch<PaginaBitacora>(`/auditoria?${consulta}`, { signal }),
    enabled: habilitada,
    placeholderData: keepPreviousData,
    retry: false,
  })
}

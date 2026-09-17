import { http } from '../../api/http'
import type {
  AliadoCrear,
  AliadoEditar,
  AliadoLeer,
  AliadoListado,
  ConvenioDeAliado,
  FiltrosAliado,
} from './types'

// Una función por endpoint de backend/src/backend/api/routers/aliado.py.

export function listarAliados(filtros: FiltrosAliado): Promise<AliadoListado> {
  return http<AliadoListado>('/aliados', { query: { ...filtros } })
}

export function consultarAliado(aliadoId: number): Promise<AliadoLeer> {
  return http<AliadoLeer>(`/aliados/${aliadoId}`)
}

export function crearAliado(datos: AliadoCrear): Promise<AliadoLeer> {
  return http<AliadoLeer>('/aliados', { method: 'POST', body: datos })
}

export function editarAliado(aliadoId: number, datos: AliadoEditar): Promise<AliadoLeer> {
  return http<AliadoLeer>(`/aliados/${aliadoId}`, { method: 'PATCH', body: datos })
}

export function inactivarAliado(aliadoId: number): Promise<AliadoLeer> {
  return http<AliadoLeer>(`/aliados/${aliadoId}/inactivar`, { method: 'POST' })
}

export function reactivarAliado(aliadoId: number): Promise<AliadoLeer> {
  return http<AliadoLeer>(`/aliados/${aliadoId}/reactivar`, { method: 'POST' })
}

export function listarConveniosDeAliado(aliadoId: number): Promise<ConvenioDeAliado[]> {
  return http<ConvenioDeAliado[]>(`/aliados/${aliadoId}/convenios`)
}

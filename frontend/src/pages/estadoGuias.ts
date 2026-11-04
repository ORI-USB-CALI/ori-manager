import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'

import { apiFetch } from '../app/api'
import { CLAVE_SESION, type CodigoRol, type Sesion, useSesion } from '../auth/sesion'
import type { CodigoGuia } from '../components/recorrido'

export type EstadoGuia = 'PENDIENTE' | 'COMPLETADO' | 'OMITIDO'
export type EstadoFinalGuia = Exclude<EstadoGuia, 'PENDIENTE'>

export interface GuiaUsuario {
  guia: CodigoGuia
  estado: EstadoGuia
  version: number | null
  actualizado_en: string | null
}

/** Conserva exactamente el contrato de claves de HU-38. El ID no viaja al servidor. */
export const claveGuia = (usuarioId: number | null, guia: CodigoGuia) => ['guias', usuarioId, guia] as const

function conservarAvance(anterior: GuiaUsuario | undefined, respuesta: GuiaUsuario): GuiaUsuario {
  const orden: Record<EstadoGuia, number> = { PENDIENTE: 0, OMITIDO: 1, COMPLETADO: 2 }
  return anterior && orden[anterior.estado] > orden[respuesta.estado] ? anterior : respuesta
}

export function useEstadoGuia(guia: CodigoGuia, habilitada: boolean) {
  const { sesion } = useSesion()
  const cliente = useQueryClient()
  const usuarioId = sesion?.id ?? null
  const clave = claveGuia(usuarioId, guia)
  return useQuery({
    queryKey: clave,
    enabled: habilitada && usuarioId !== null,
    queryFn: async ({ signal }) => {
      const respuesta = await consultarGuia(guia, signal)
      return conservarAvance(cliente.getQueryData<GuiaUsuario>(clave), respuesta)
    },
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

interface RegistroGuia {
  usuarioId: number
  rol: CodigoRol
  guia: CodigoGuia
  version: number
  estado: EstadoFinalGuia
}

/** Escritura individual, cancelación de lecturas obsoletas y protección tras logout. */
export function useRegistrarEstadoGuia(guia: CodigoGuia, version: number) {
  const { sesion } = useSesion()
  const cliente = useQueryClient()
  const vigente = useRef(true)
  const enCurso = useRef(new Map<string, Promise<GuiaUsuario>>())
  useEffect(() => {
    vigente.current = true
    return () => { vigente.current = false }
  }, [])
  const perteneceASesion = useCallback((registro: RegistroGuia) => {
    const actual = cliente.getQueryData<Sesion | null>(CLAVE_SESION)
    return vigente.current && actual?.id === registro.usuarioId && actual.rol.codigo === registro.rol
  }, [cliente])
  const mutacion = useMutation({
    mutationFn: async (registro: RegistroGuia) => {
      if (!perteneceASesion(registro)) throw new Error('La sesión ha cambiado')
      await cliente.cancelQueries({ queryKey: claveGuia(registro.usuarioId, registro.guia), exact: true })
      if (!perteneceASesion(registro)) throw new Error('La sesión ha cambiado')
      return actualizarGuia(registro.guia, registro.estado, registro.version)
    },
    retry: false,
    onSuccess: (respuesta, registro) => {
      if (!perteneceASesion(registro)) return
      cliente.setQueryData<GuiaUsuario>(claveGuia(registro.usuarioId, registro.guia),
        (anterior) => conservarAvance(anterior, respuesta))
    },
  })
  const { mutateAsync } = mutacion
  const registrar = useCallback((estado: EstadoFinalGuia) => {
    if (!sesion) return Promise.reject(new Error('No hay sesión activa'))
    const registro = { usuarioId: sesion.id, rol: sesion.rol.codigo, guia, version, estado }
    if (!perteneceASesion(registro)) return Promise.reject(new Error('La sesión ha cambiado'))
    const identidad = `${registro.usuarioId}:${guia}`
    const existente = enCurso.current.get(identidad)
    if (existente) return existente
    const peticion = mutateAsync(registro).finally(() => { enCurso.current.delete(identidad) })
    enCurso.current.set(identidad, peticion)
    return peticion
  }, [guia, mutateAsync, perteneceASesion, sesion, version])
  return { ...mutacion, registrar }
}

/** Consulta la guía del usuario autenticado. Nunca se envía un ID de usuario. */
export function consultarGuia(guia: CodigoGuia, signal?: AbortSignal): Promise<GuiaUsuario> {
  return apiFetch<GuiaUsuario>(`/guias/${guia}`, { signal })
}

/** El backend conserva COMPLETADO como estado irreversible. */
export function actualizarGuia(guia: CodigoGuia, estado: EstadoFinalGuia, version: number): Promise<GuiaUsuario> {
  return apiFetch<GuiaUsuario>(`/guias/${guia}`, {
    method: 'PUT',
    body: JSON.stringify({ estado, version }),
  })
}

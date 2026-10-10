import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { apiFetch } from '../app/api'

export type TipoNotificacion =
  | 'REVISION_JURIDICA_PENDIENTE'
  | 'DEVOLUCION_REVISION'
  | 'SOLICITUD_DEVUELTA'
  | 'REVISION_CONTRAPARTE_PENDIENTE'

export type EntidadNotificacion = 'CONVENIO' | 'SOLICITUD'

export interface Notificacion {
  id: number
  tipo: TipoNotificacion
  entidad_tipo: EntidadNotificacion
  entidad_id: number
  mensaje: string
  leida: boolean
  leida_en: string | null
  resuelta: boolean
  resuelta_en: string | null
  creado_en: string
}

export const CLAVE_NOTIFICACIONES = ['notificaciones'] as const

export function obtenerNotificaciones() {
  return apiFetch<Notificacion[]>('/notificaciones')
}

export function useNotificaciones(habilitada: boolean) {
  return useQuery({
    queryKey: CLAVE_NOTIFICACIONES,
    queryFn: obtenerNotificaciones,
    enabled: habilitada,
    retry: false,
    refetchOnMount: 'always',
  })
}

export function useMarcarNotificacionLeida() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Notificacion>(`/notificaciones/${id}/leida`, { method: 'PATCH' }),
    onSuccess: (actualizada) => {
      queryClient.setQueryData<Notificacion[]>(CLAVE_NOTIFICACIONES, (actuales) =>
        actuales?.map((item) => (item.id === actualizada.id ? actualizada : item)),
      )
    },
  })
}

function urlNotificacionesWs(): string {
  const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocolo}://${window.location.host}/api/notificaciones/ws`
}

/**
 * HU-33 tarea 5: abre el WebSocket nativo de FastAPI y, cuando el backend
 * avisa un cambio, invalida la query para que se vuelva a pedir por REST.
 * Reconecta con backoff simple si el socket se cae (red, deploy, etc.).
 */
export function useNotificacionesTiempoReal(habilitada: boolean) {
  const queryClient = useQueryClient()
  const intentoRef = useRef(0)

  useEffect(() => {
    if (!habilitada) return

    let socket: WebSocket | null = null
    let cerradoPorLimpieza = false
    let temporizador: number | undefined

    const conectar = () => {
      socket = new WebSocket(urlNotificacionesWs())

      socket.onmessage = () => {
        void queryClient.invalidateQueries({ queryKey: CLAVE_NOTIFICACIONES })
      }

      socket.onopen = () => {
        intentoRef.current = 0
      }

      socket.onclose = (evento) => {
        if (cerradoPorLimpieza || evento.code === 1008) return
        const espera = Math.min(30_000, 1000 * 2 ** intentoRef.current)
        intentoRef.current += 1
        temporizador = window.setTimeout(conectar, espera)
      }
    }

    conectar()

    return () => {
      cerradoPorLimpieza = true
      window.clearTimeout(temporizador)
      socket?.close()
    }
  }, [habilitada, queryClient])
}

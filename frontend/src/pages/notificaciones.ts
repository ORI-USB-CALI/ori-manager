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

/** Una tarea resuelta ya no está pendiente, aunque no se haya marcado leída. */
export function contarPendientes(notificaciones: Notificacion[] | undefined): number {
  return notificaciones?.filter((item) => !item.resuelta).length ?? 0
}

async function obtenerTicketWs(): Promise<string> {
  const { ticket } = await apiFetch<{ ticket: string }>('/notificaciones/ws-ticket', {
    method: 'POST',
  })
  return ticket
}

/**
 * En Render el frontend es un static site: no puede alojar ni hacer proxy
 * de un WebSocket, así que la conexión va directo a la URL pública del
 * backend (`VITE_WS_BACKEND_URL`). En desarrollo local esa variable no
 * existe y se usa el mismo origen, que el proxy de Vite sí reenvía.
 */
function urlNotificacionesWs(ticket: string): string {
  const base = import.meta.env.VITE_WS_BACKEND_URL
  const parametro = `ticket=${encodeURIComponent(ticket)}`
  if (base) {
    const wsBase = base.replace(/^http/, 'ws').replace(/\/$/, '')
    return `${wsBase}/api/notificaciones/ws?${parametro}`
  }
  const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocolo}://${window.location.host}/api/notificaciones/ws?${parametro}`
}

/**
 * HU-33 tarea 5: abre el WebSocket nativo de FastAPI y, cuando el backend
 * avisa un cambio, invalida la query para que se vuelva a pedir por REST.
 * Reconecta con backoff simple si el socket se cae (red, deploy, etc.); un
 * cierre 1008 (ticket inválido/expirado, cuenta desactivada) no reintenta.
 *
 * Mecanismo de recuperación (code review HU-33 PR): el servidor nunca
 * reenvía eventos que ocurrieron mientras el socket estuvo caído, solo el
 * último "algo cambió". Por eso, cada vez que la conexión abre (la primera
 * vez o tras una reconexión), se invalida la query igual que si hubiera
 * llegado un mensaje: así se recupera cualquier cambio perdido durante el
 * tiempo que el socket estuvo desconectado, no solo los que lleguen
 * después de reconectar.
 *
 * Cada conexión usa un ticket de un solo uso (ver `obtenerTicketWs`): la
 * cookie de sesión no viaja hasta el dominio del backend en Render.
 */
export function useNotificacionesTiempoReal(habilitada: boolean) {
  const queryClient = useQueryClient()
  const intentoRef = useRef(0)

  useEffect(() => {
    if (!habilitada) return

    let socket: WebSocket | null = null
    let cancelado = false
    let temporizador: number | undefined

    const conectar = () => {
      void obtenerTicketWs()
        .then((ticket) => {
          if (cancelado) return
          socket = new WebSocket(urlNotificacionesWs(ticket))

          socket.onmessage = () => {
            void queryClient.invalidateQueries({ queryKey: CLAVE_NOTIFICACIONES })
          }

          socket.onopen = () => {
            intentoRef.current = 0
            void queryClient.invalidateQueries({ queryKey: CLAVE_NOTIFICACIONES })
          }

          socket.onclose = (evento) => {
            if (cancelado || evento.code === 1008) return
            const espera = Math.min(30_000, 1000 * 2 ** intentoRef.current)
            intentoRef.current += 1
            temporizador = window.setTimeout(conectar, espera)
          }
        })
        .catch(() => {
          if (cancelado) return
          const espera = Math.min(30_000, 1000 * 2 ** intentoRef.current)
          intentoRef.current += 1
          temporizador = window.setTimeout(conectar, espera)
        })
    }

    conectar()

    return () => {
      cancelado = true
      window.clearTimeout(temporizador)
      socket?.close()
    }
  }, [habilitada, queryClient])
}

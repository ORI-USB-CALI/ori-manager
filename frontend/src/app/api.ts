import { nombreArchivoDesdeContentDisposition } from './descargas'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface ErrorValidacion {
  loc?: Array<string | number>
  msg?: string
}

function mensajeError(cuerpo: unknown, statusText: string): string {
  if (!cuerpo || typeof cuerpo !== 'object' || !('detail' in cuerpo)) return statusText
  const detalle = cuerpo.detail
  if (typeof detalle === 'string') return detalle
  if (!Array.isArray(detalle)) {
    if (detalle && typeof detalle === 'object' && 'message' in detalle && typeof detalle.message === 'string') {
      return detalle.message
    }
    return statusText
  }

  return detalle
    .map((error: ErrorValidacion) => {
      const campo = error.loc?.at(-1)
      const mensaje = error.msg?.replace(/^Value error, /, '') ?? 'Valor inválido'
      return campo ? `${String(campo)}: ${mensaje}` : mensaje
    })
    .join('. ')
}

export async function apiFetch<T>(ruta: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const respuesta = await fetch(`/api${ruta}`, {
    ...init,
    credentials: 'include',
    headers,
  })

  if (!respuesta.ok) {
    const cuerpo: unknown = await respuesta.json().catch(() => null)
    const detail = cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo ? cuerpo.detail : undefined
    throw new ApiError(respuesta.status, mensajeError(cuerpo, respuesta.statusText), detail)
  }

  if (respuesta.status === 204) return undefined as T
  return respuesta.json() as Promise<T>
}

function leerJson(texto: string): unknown {
  try {
    return JSON.parse(texto)
  } catch {
    return null
  }
}

export interface ArchivoDescargado {
  blob: Blob
  nombreArchivo: string | null
}

/**
 * Pide un archivo binario a la API. Si el cuerpo del error no trae `detail`
 * (como el 422 de exportación de HU-24), el cuerpo completo queda en `detail`.
 */
export async function apiFetchArchivo(ruta: string): Promise<ArchivoDescargado> {
  const respuesta = await fetch(`/api${ruta}`, { credentials: 'include' })

  if (!respuesta.ok) {
    const cuerpo = leerJson(await respuesta.text().catch(() => ''))
    const detail = cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo ? cuerpo.detail : cuerpo
    const mensaje = cuerpo && typeof cuerpo === 'object' && !('detail' in cuerpo)
      && 'message' in cuerpo && typeof cuerpo.message === 'string'
      ? cuerpo.message
      : mensajeError(cuerpo, respuesta.statusText)
    throw new ApiError(respuesta.status, mensaje, detail ?? undefined)
  }

  return {
    blob: await respuesta.blob(),
    nombreArchivo: nombreArchivoDesdeContentDisposition(respuesta.headers.get('Content-Disposition')),
  }
}

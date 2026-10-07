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

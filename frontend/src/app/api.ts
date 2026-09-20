export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
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
  if (!Array.isArray(detalle)) return statusText

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
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const respuesta = await fetch(`/api${ruta}`, {
    ...init,
    credentials: 'include',
    headers,
  })

  if (!respuesta.ok) {
    const cuerpo: unknown = await respuesta.json().catch(() => null)
    throw new ApiError(respuesta.status, mensajeError(cuerpo, respuesta.statusText))
  }

  if (respuesta.status === 204) return undefined as T
  return respuesta.json() as Promise<T>
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Único punto de acceso HTTP. `/api` va por el proxy de Vite (mismo origen, viaja la cookie).
export async function apiFetch<T>(ruta: string, init?: RequestInit): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => null)
    // FastAPI devuelve `detail` como texto, o como lista de errores de validación (422).
    const detalle =
      typeof cuerpo?.detail === 'string'
        ? cuerpo.detail
        : Array.isArray(cuerpo?.detail)
          ? cuerpo.detail.map((error: { msg: string }) => error.msg.replace(/^Value error, /, '')).join('. ')
          : respuesta.statusText
    throw new ApiError(respuesta.status, detalle)
  }

  return respuesta.json() as Promise<T>
}

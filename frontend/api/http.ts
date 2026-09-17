const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

function extractErrorMessage(details: unknown): string | undefined {
  if (details && typeof details === 'object' && 'detail' in details) {
    const detail = (details as { detail: unknown }).detail

    if (typeof detail === 'string') {
      return detail
    }

    // FastAPI/Pydantic devuelve una lista de errores de validacion (422)
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === 'object' && item && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join(' | ')
    }
  }

  return undefined
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    let details: unknown

    try {
      details = await response.json()
    } catch {
      details = undefined
    }

    const message =
      extractErrorMessage(details) ?? `Error ${response.status} al comunicarse con el servidor`

    throw new ApiError(message, response.status, details)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

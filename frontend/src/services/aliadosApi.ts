import type { AliadoDetalle } from '../types/aliado'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

export async function fetchAliadoDetalle(aliadoId: string): Promise<AliadoDetalle> {
  const response = await fetch(`/api/v1/aliados/${aliadoId}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer session_token',
      'X-User-Permissions': 'aliados:read, convenios:read',
    },
  })

  if (!response.ok) {
    if (response.status === 404) {
      throw new ApiError('Aliado no encontrado', 404)
    }
    if (response.status === 403) {
      throw new ApiError('No tiene permisos para consultar este aliado', 403)
    }
    if (response.status === 401) {
      throw new ApiError('Sesión no iniciada o token no válido', 401)
    }
    throw new ApiError(`Error al consultar el aliado (${response.status})`, response.status)
  }

  return response.json()
}

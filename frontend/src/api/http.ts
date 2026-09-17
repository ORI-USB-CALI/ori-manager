import type { RolUsuario } from '../features/aliados/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// El backend recibe el rol por header hasta que exista autenticación (HU-01).
// Se guarda en localStorage para que el selector de la barra superior lo cambie.
const CLAVE_ROL = 'ori.rol'
const ROL_POR_DEFECTO: RolUsuario = 'gestor_ori'

export function obtenerRol(): RolUsuario {
  try {
    return (localStorage.getItem(CLAVE_ROL) as RolUsuario | null) ?? ROL_POR_DEFECTO
  } catch {
    return ROL_POR_DEFECTO
  }
}

export function guardarRol(rol: RolUsuario): void {
  try {
    localStorage.setItem(CLAVE_ROL, rol)
  } catch {
    // Sin almacenamiento disponible: se usa el rol por defecto.
  }
}

export function puedeGestionar(rol: RolUsuario): boolean {
  return rol === 'administrador_ori' || rol === 'gestor_ori'
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type Query = Record<string, string | number | undefined>

interface Opciones {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  query?: Query
}

function construirUrl(path: string, query?: Query): string {
  const url = new URL(path, BASE_URL)
  for (const [clave, valor] of Object.entries(query ?? {})) {
    if (valor !== undefined && valor !== '') {
      url.searchParams.set(clave, String(valor))
    }
  }
  return url.toString()
}

async function extraerDetalle(response: Response): Promise<string> {
  try {
    const cuerpo = await response.json()
    if (typeof cuerpo.detail === 'string') return cuerpo.detail
    if (Array.isArray(cuerpo.detail)) {
      return cuerpo.detail.map((e: { msg?: string }) => e.msg ?? '').join('. ')
    }
  } catch {
    // Sin cuerpo JSON: se usa el mensaje genérico.
  }
  return `Error ${response.status} al consultar la API`
}

export async function http<T>(path: string, opciones: Opciones = {}): Promise<T> {
  const response = await fetch(construirUrl(path, opciones.query), {
    method: opciones.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Rol-Usuario': obtenerRol(),
    },
    body: opciones.body === undefined ? undefined : JSON.stringify(opciones.body),
  })

  if (!response.ok) {
    throw new ApiError(await extraerDetalle(response), response.status)
  }

  return response.json() as Promise<T>
}

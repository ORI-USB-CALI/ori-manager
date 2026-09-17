import type {
  UsuarioActualizar,
  UsuarioCambiarRol,
  UsuarioCrear,
  UsuarioLeer,
  UsuarioListar,
} from './types'

// Integración real contra backend/src/backend/api/rutas_usuario.py
// (rama feature/HU03-CRUD-de-usuarios). Ver mockData.ts si se necesita
// volver a datos de prueba sin backend disponible.

const API_BASE_URL = import.meta.env.VITE_API_URL

async function leerRespuesta<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    let mensaje = `Error ${respuesta.status} al comunicarse con el servidor.`
    try {
      const cuerpo: unknown = await respuesta.json()
      if (
        cuerpo &&
        typeof cuerpo === 'object' &&
        'detail' in cuerpo &&
        typeof (cuerpo as { detail: unknown }).detail === 'string'
      ) {
        mensaje = (cuerpo as { detail: string }).detail
      }
    } catch {
      // el cuerpo no era JSON (p. ej. error 500 sin detalle); se usa el mensaje genérico
    }
    throw new Error(mensaje)
  }
  return respuesta.json() as Promise<T>
}

export async function listarUsuarios(): Promise<UsuarioListar[]> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/`)
  return leerRespuesta<UsuarioListar[]>(respuesta)
}

export async function obtenerUsuario(id: number): Promise<UsuarioLeer> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/${id}`)
  return leerRespuesta<UsuarioLeer>(respuesta)
}

export async function crearUsuario(datos: UsuarioCrear): Promise<UsuarioLeer> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })
  return leerRespuesta<UsuarioLeer>(respuesta)
}

export async function editarUsuario(
  id: number,
  datos: UsuarioActualizar,
): Promise<UsuarioLeer> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })
  return leerRespuesta<UsuarioLeer>(respuesta)
}

export async function cambiarRolUsuario(
  id: number,
  datos: UsuarioCambiarRol,
): Promise<UsuarioLeer> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/${id}/rol`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })
  return leerRespuesta<UsuarioLeer>(respuesta)
}

export async function desactivarUsuario(id: number): Promise<UsuarioLeer> {
  const respuesta = await fetch(`${API_BASE_URL}/usuarios/${id}/desactivar`, {
    method: 'POST',
  })
  return leerRespuesta<UsuarioLeer>(respuesta)
}

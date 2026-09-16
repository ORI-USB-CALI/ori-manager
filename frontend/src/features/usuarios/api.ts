import { USUARIOS_MOCK } from './mockData'
import { ROLES_INTERNOS } from './types'
import type {
  CodigoRol,
  RolLeer,
  UsuarioActualizar,
  UsuarioCambiarRol,
  UsuarioCrear,
  UsuarioLeer,
  UsuarioListar,
} from './types'

// Capa swappable: replica 1:1 las 5 operaciones de
// backend/src/backend/api/rutas_usuario.py (rama de Jesús). Para conectar la
// API real, cambiar el cuerpo de cada función por un fetch a
// `${import.meta.env.VITE_API_URL}/usuarios/...` manteniendo la firma; el
// resto de la app (hooks, páginas) no debería necesitar cambios.
//
// obtenerUsuario() es la excepción: ese endpoint no existe todavía en la
// rama de Jesús (no hay GET /usuarios/{id}). Se agregó aquí solo para poder
// precargar el formulario de edición; cuando el backend lo defina, ajustar
// esta función a la ruta real.

const RETRASO_SIMULADO_MS = 300

function retraso(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, RETRASO_SIMULADO_MS))
}

function rolPorCodigo(codigo: CodigoRol): RolLeer {
  const rol = ROLES_INTERNOS.find((r) => r.codigo === codigo)
  if (!rol) {
    throw new Error('Rol no valido')
  }
  return rol
}

let usuarios: UsuarioLeer[] = USUARIOS_MOCK.map((usuario) => ({ ...usuario }))
let siguienteId = Math.max(...usuarios.map((u) => u.id)) + 1

export async function listarUsuarios(): Promise<UsuarioListar[]> {
  await retraso()
  return usuarios.map(({ id, correo, nombre_completo, rol, activo }) => ({
    id,
    correo,
    nombre_completo,
    rol,
    activo,
  }))
}

export async function obtenerUsuario(id: number): Promise<UsuarioLeer> {
  await retraso()
  const usuario = usuarios.find((u) => u.id === id)
  if (!usuario) {
    throw new Error('Usuario no encontrado')
  }
  return { ...usuario }
}

export async function crearUsuario(datos: UsuarioCrear): Promise<UsuarioLeer> {
  await retraso()
  const correoDuplicado = usuarios.some(
    (u) => u.correo.toLowerCase() === datos.correo.toLowerCase(),
  )
  if (correoDuplicado) {
    throw new Error('El correo ya existe')
  }

  const nuevoUsuario: UsuarioLeer = {
    id: siguienteId++,
    correo: datos.correo,
    nombre_completo: datos.nombre_completo,
    documento_identidad: datos.documento_identidad ?? null,
    telefono: datos.telefono ?? null,
    cargo: datos.cargo ?? null,
    rol: rolPorCodigo(datos.rol),
    activo: true,
    ultimo_acceso: null,
  }

  usuarios = [...usuarios, nuevoUsuario]
  return { ...nuevoUsuario }
}

export async function editarUsuario(
  id: number,
  datos: UsuarioActualizar,
): Promise<UsuarioLeer> {
  await retraso()
  const usuario = usuarios.find((u) => u.id === id)
  if (!usuario) {
    throw new Error('Usuario no encontrado')
  }

  const actualizado: UsuarioLeer = { ...usuario, ...datos }
  usuarios = usuarios.map((u) => (u.id === id ? actualizado : u))
  return { ...actualizado }
}

export async function cambiarRolUsuario(
  id: number,
  datos: UsuarioCambiarRol,
): Promise<UsuarioLeer> {
  await retraso()
  const usuario = usuarios.find((u) => u.id === id)
  if (!usuario) {
    throw new Error('Usuario no encontrado')
  }

  const actualizado: UsuarioLeer = { ...usuario, rol: rolPorCodigo(datos.rol) }
  usuarios = usuarios.map((u) => (u.id === id ? actualizado : u))
  return { ...actualizado }
}

export async function desactivarUsuario(id: number): Promise<{ mensaje: string }> {
  await retraso()
  const usuario = usuarios.find((u) => u.id === id)
  if (!usuario) {
    throw new Error('Usuario no encontrado')
  }
  if (!usuario.activo) {
    throw new Error('El usuario ya esta inactivo')
  }

  usuarios = usuarios.map((u) => (u.id === id ? { ...u, activo: false } : u))
  return { mensaje: 'Usuario desactivado correctamente' }
}

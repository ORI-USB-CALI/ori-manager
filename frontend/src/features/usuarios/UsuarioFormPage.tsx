import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useCambiarRolUsuario, useCrearUsuario, useEditarUsuario, useUsuario } from './hooks'
import type { CodigoRol, UsuarioLeer } from './types'
import { ROLES_INTERNOS } from './types'
import './usuarios.css'

interface CamposFormulario {
  correo: string
  contrasena: string
  nombreCompleto: string
  documentoIdentidad: string
  telefono: string
  cargo: string
  rol: CodigoRol | ''
}

const FORMULARIO_VACIO: CamposFormulario = {
  correo: '',
  contrasena: '',
  nombreCompleto: '',
  documentoIdentidad: '',
  telefono: '',
  cargo: '',
  rol: '',
}

function camposDesdeUsuario(usuario: UsuarioLeer): CamposFormulario {
  return {
    correo: usuario.correo,
    contrasena: '',
    nombreCompleto: usuario.nombre_completo,
    documentoIdentidad: usuario.documento_identidad ?? '',
    telefono: usuario.telefono ?? '',
    cargo: usuario.cargo ?? '',
    rol: usuario.rol.codigo,
  }
}

const CORREO_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function UsuarioFormPage() {
  const { id } = useParams<{ id: string }>()
  const usuarioId = id ? Number(id) : undefined
  const modoEdicion = usuarioId !== undefined

  const { data: usuarioActual, isPending: cargandoUsuario } = useUsuario(usuarioId)

  if (modoEdicion && cargandoUsuario) {
    return (
      <main className="usuario-form">
        <p>Cargando datos del usuario…</p>
      </main>
    )
  }

  // key fuerza un remontaje por usuario: el estado inicial del formulario
  // solo se calcula una vez, ya con los datos cargados (evita setState en
  // un efecto solo para precargar valores iniciales).
  return (
    <FormularioUsuario
      key={usuarioId ?? 'nuevo'}
      usuarioId={usuarioId}
      usuarioActual={modoEdicion ? usuarioActual : undefined}
    />
  )
}

interface FormularioUsuarioProps {
  usuarioId: number | undefined
  usuarioActual: UsuarioLeer | undefined
}

function FormularioUsuario({ usuarioId, usuarioActual }: FormularioUsuarioProps) {
  const modoEdicion = usuarioId !== undefined
  const navigate = useNavigate()

  const crearUsuario = useCrearUsuario()
  const editarUsuario = useEditarUsuario(usuarioId ?? -1)
  const cambiarRolUsuario = useCambiarRolUsuario(usuarioId ?? -1)

  const [campos, setCampos] = useState<CamposFormulario>(() =>
    usuarioActual ? camposDesdeUsuario(usuarioActual) : FORMULARIO_VACIO,
  )
  const [errores, setErrores] = useState<Partial<Record<keyof CamposFormulario, string>>>({})
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null)

  function actualizarCampo<K extends keyof CamposFormulario>(campo: K, valor: CamposFormulario[K]) {
    setCampos((anterior) => ({ ...anterior, [campo]: valor }))
  }

  function validar(): Partial<Record<keyof CamposFormulario, string>> {
    const nuevosErrores: Partial<Record<keyof CamposFormulario, string>> = {}

    if (!campos.correo.trim()) {
      nuevosErrores.correo = 'El correo es obligatorio.'
    } else if (!CORREO_REGEX.test(campos.correo.trim())) {
      nuevosErrores.correo = 'El correo no tiene un formato válido.'
    }

    if (!modoEdicion && campos.contrasena.length < 8) {
      nuevosErrores.contrasena = 'La contraseña debe tener al menos 8 caracteres.'
    }

    if (!campos.nombreCompleto.trim()) {
      nuevosErrores.nombreCompleto = 'El nombre completo es obligatorio.'
    }

    if (!campos.rol) {
      nuevosErrores.rol = 'Debes asignar un rol interno.'
    }

    return nuevosErrores
  }

  async function manejarSubmit(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setErrorGeneral(null)

    const nuevosErrores = validar()
    setErrores(nuevosErrores)
    if (Object.keys(nuevosErrores).length > 0) return

    const rolSeleccionado = campos.rol as CodigoRol

    try {
      if (modoEdicion && usuarioId !== undefined) {
        await editarUsuario.mutateAsync({
          nombre_completo: campos.nombreCompleto.trim(),
          documento_identidad: campos.documentoIdentidad.trim() || null,
          telefono: campos.telefono.trim() || null,
          cargo: campos.cargo.trim() || null,
        })

        if (usuarioActual && rolSeleccionado !== usuarioActual.rol.codigo) {
          await cambiarRolUsuario.mutateAsync({ rol: rolSeleccionado })
        }
      } else {
        await crearUsuario.mutateAsync({
          correo: campos.correo.trim(),
          contrasena: campos.contrasena,
          nombre_completo: campos.nombreCompleto.trim(),
          rol: rolSeleccionado,
          documento_identidad: campos.documentoIdentidad.trim() || null,
          telefono: campos.telefono.trim() || null,
          cargo: campos.cargo.trim() || null,
        })
      }

      navigate('/usuarios')
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo guardar el usuario.'
      // CA-04: el backend real rechaza con "El correo ya existe" (400).
      if (mensaje.toLowerCase().includes('correo')) {
        setErrores((anterior) => ({ ...anterior, correo: mensaje }))
      } else {
        setErrorGeneral(mensaje)
      }
    }
  }

  const guardando = crearUsuario.isPending || editarUsuario.isPending || cambiarRolUsuario.isPending

  return (
    <main className="usuario-form">
      <h1>{modoEdicion ? 'Editar usuario' : 'Nuevo usuario'}</h1>
      <p>
        {modoEdicion
          ? 'Los campos no modificados conservan su valor actual.'
          : 'Solo se pueden crear usuarios con roles internos (Administrador, Gestor o Revisor ORI).'}
      </p>

      {errorGeneral && <div className="usuario-form__error-general">{errorGeneral}</div>}

      <form onSubmit={manejarSubmit} noValidate>
        <div className="form-group">
          <label htmlFor="correo" className="form-label">Correo</label>
          <input
            id="correo"
            type="email"
            className={`form-control ${errores.correo ? 'is-invalid' : ''}`}
            value={campos.correo}
            disabled={modoEdicion}
            onChange={(evento) => actualizarCampo('correo', evento.target.value)}
          />
          {errores.correo && <p className="form-error">{errores.correo}</p>}
        </div>

        {!modoEdicion && (
          <div className="form-group">
            <label htmlFor="contrasena" className="form-label">Contraseña</label>
            <input
              id="contrasena"
              type="password"
              className={`form-control ${errores.contrasena ? 'is-invalid' : ''}`}
              value={campos.contrasena}
              onChange={(evento) => actualizarCampo('contrasena', evento.target.value)}
            />
            {errores.contrasena && <p className="form-error">{errores.contrasena}</p>}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="nombreCompleto" className="form-label">Nombre completo</label>
          <input
            id="nombreCompleto"
            type="text"
            className={`form-control ${errores.nombreCompleto ? 'is-invalid' : ''}`}
            value={campos.nombreCompleto}
            onChange={(evento) => actualizarCampo('nombreCompleto', evento.target.value)}
          />
          {errores.nombreCompleto && <p className="form-error">{errores.nombreCompleto}</p>}
        </div>

        <div className="form-group">
          <label htmlFor="rol" className="form-label">Rol interno</label>
          <select
            id="rol"
            className={`form-control ${errores.rol ? 'is-invalid' : ''}`}
            value={campos.rol}
            onChange={(evento) => actualizarCampo('rol', evento.target.value as CodigoRol)}
          >
            <option value="">Selecciona un rol…</option>
            {ROLES_INTERNOS.map((rol) => (
              <option key={rol.codigo} value={rol.codigo}>
                {rol.nombre}
              </option>
            ))}
          </select>
          {errores.rol && <p className="form-error">{errores.rol}</p>}
        </div>

        <div className="form-group">
          <label htmlFor="documentoIdentidad" className="form-label">Documento de identidad</label>
          <input
            id="documentoIdentidad"
            type="text"
            className="form-control"
            value={campos.documentoIdentidad}
            onChange={(evento) => actualizarCampo('documentoIdentidad', evento.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="telefono" className="form-label">Teléfono</label>
          <input
            id="telefono"
            type="text"
            className="form-control"
            value={campos.telefono}
            onChange={(evento) => actualizarCampo('telefono', evento.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="cargo" className="form-label">Cargo</label>
          <input
            id="cargo"
            type="text"
            className="form-control"
            value={campos.cargo}
            onChange={(evento) => actualizarCampo('cargo', evento.target.value)}
          />
        </div>

        <div className="usuario-form__acciones">
          <button type="submit" className="btn btn-primary" disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
          <Link to="/usuarios" className="btn btn-outline">
            Cancelar
          </Link>
        </div>
      </form>
    </main>
  )
}

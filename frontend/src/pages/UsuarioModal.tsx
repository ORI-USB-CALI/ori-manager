import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef } from 'react'

import { apiFetch } from '../app/api'
import { Select } from '../components/Select'
import { ETIQUETAS_ROL, type Rol } from '../auth/sesion'

export interface Usuario {
  id: string
  email: string
  is_active: boolean
  rol: Rol
}

const OPCIONES_ROL = Object.entries(ETIQUETAS_ROL).map(([value, label]) => ({ value, label }))
const OPCIONES_ESTADO = [
  { value: 'activo', label: 'Activo' },
  { value: 'inactivo', label: 'Inactivo' },
]

interface Props {
  // Sin usuario = crear; con usuario = editar.
  usuario?: Usuario
  esPropio?: boolean
  onGuardado: () => Promise<unknown>
  onCerrar: () => void
}

export function UsuarioModal({ usuario, esPropio = false, onGuardado, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)
  const guardar = useMutation({
    mutationFn: (datos: Record<string, unknown>) =>
      usuario
        ? apiFetch<Usuario>(`/usuarios/${usuario.id}`, { method: 'PATCH', body: JSON.stringify(datos) })
        : apiFetch<Usuario>('/usuarios', { method: 'POST', body: JSON.stringify(datos) }),
    onSuccess: async () => {
      await onGuardado()
      dialogo.current?.close()
    },
  })

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const datos: Record<string, unknown> = { email: form.get('email') }
    const password = String(form.get('password') ?? '')
    if (password) datos.password = password
    // Un admin no cambia su propio rol ni se desactiva (el backend también lo rechaza).
    if (!esPropio) {
      datos.rol = form.get('rol')
      if (usuario) datos.is_active = form.get('estado') === 'activo'
    }
    guardar.mutate(datos)
  }

  return (
    <dialog ref={dialogo} className="modal" onClose={onCerrar} aria-labelledby="usuario-modal-titulo">
      <form onSubmit={enviar}>
        <h3 id="usuario-modal-titulo">{usuario ? 'Editar usuario' : 'Nuevo usuario'}</h3>

        {guardar.isError && (
          <p className="alert-error" role="alert">
            {guardar.error.message}
          </p>
        )}

        <div className="form-group">
          <label className="form-label" htmlFor="usuario-email">
            Correo
          </label>
          <input
            id="usuario-email"
            name="email"
            type="email"
            className="form-control"
            defaultValue={usuario?.email}
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="usuario-password">
            {usuario ? 'Nueva contraseña' : 'Contraseña'}
          </label>
          <input
            id="usuario-password"
            name="password"
            type="password"
            className="form-control"
            minLength={8}
            maxLength={72}
            required={!usuario}
            autoComplete="new-password"
            placeholder={usuario ? 'Dejar vacío para no cambiarla' : 'Mínimo 8 caracteres'}
          />
        </div>

        <Select
          id="usuario-rol"
          name="rol"
          label="Rol"
          opciones={OPCIONES_ROL}
          defaultValue={usuario?.rol ?? 'usuario_ori'}
          disabled={esPropio}
        />

        {usuario && (
          <Select
            id="usuario-estado"
            name="estado"
            label="Estado"
            opciones={OPCIONES_ESTADO}
            defaultValue={usuario.is_active ? 'activo' : 'inactivo'}
            disabled={esPropio}
          />
        )}

        {esPropio && <small>No puede cambiar su propio rol ni desactivarse.</small>}

        <div className="modal-acciones">
          <button type="button" className="btn btn-outline" onClick={() => dialogo.current?.close()}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={guardar.isPending}>
            {guardar.isPending ? 'Guardando…' : usuario ? 'Guardar cambios' : 'Crear usuario'}
          </button>
        </div>
      </form>
    </dialog>
  )
}

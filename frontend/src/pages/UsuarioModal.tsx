import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import {
  CLAVE_SESION,
  type CodigoRol,
  type TipoUsuario,
  useSesion,
} from '../auth/sesion'
import { Select } from '../components/Select'
import {
  OPCIONES_TIPO,
  type Usuario,
  etiquetaTipo,
  opcionesRol,
} from './usuarios'

interface Props {
  usuario?: Usuario
  onGuardado: (mensaje: string) => Promise<unknown>
  onCerrar: () => void
}

function texto(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'No fue posible completar la operación.'
}

function valorFormulario(form: FormData, campo: string): string {
  return String(form.get(campo) ?? '').trim()
}

export function UsuarioModal({ usuario, onGuardado, onCerrar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null)
  const queryClient = useQueryClient()
  const { sesion, puede } = useSesion()
  const esPropio = usuario?.id === sesion?.id
  const [tipo, setTipo] = useState<TipoUsuario>(usuario?.tipo_usuario ?? 'INTERNO')
  const [rol, setRol] = useState<CodigoRol>(usuario?.rol.codigo ?? 'GESTOR_ORI')

  async function completar(mensaje: string, afectaSesion = false) {
    await onGuardado(mensaje)
    if (afectaSesion) {
      await queryClient.invalidateQueries({ queryKey: CLAVE_SESION })
    }
    dialogo.current?.close()
  }

  const guardar = useMutation({
    mutationFn: (datos: Record<string, unknown>) =>
      usuario
        ? apiFetch<Usuario>(`/usuarios/${usuario.id}`, {
            method: 'PATCH',
            body: JSON.stringify(datos),
          })
        : apiFetch<Usuario>('/usuarios', {
            method: 'POST',
            body: JSON.stringify(datos),
          }),
    onSuccess: () => completar(usuario ? 'Datos actualizados.' : 'Usuario creado.', esPropio),
  })

  const cambiarRol = useMutation({
    mutationFn: (codigo: CodigoRol) =>
      apiFetch<Usuario>(`/usuarios/${usuario?.id}/rol`, {
        method: 'PATCH',
        body: JSON.stringify({ rol: codigo }),
      }),
    onSuccess: () => completar('Rol actualizado.'),
  })

  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) =>
      apiFetch<Usuario>(`/usuarios/${usuario?.id}/estado`, {
        method: 'PATCH',
        body: JSON.stringify({ activo }),
      }),
    onSuccess: () => completar(usuario?.activo ? 'Usuario desactivado.' : 'Usuario activado.'),
  })

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  function cambiarTipo(nuevoTipo: TipoUsuario) {
    setTipo(nuevoTipo)
    setRol(opcionesRol(nuevoTipo)[0].value as CodigoRol)
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const contrasena = String(form.get('contrasena') ?? '')

    if (!usuario) {
      const datos: Record<string, unknown> = {
        correo: valorFormulario(form, 'correo'),
        contrasena,
        nombre_completo: valorFormulario(form, 'nombre_completo'),
        tipo_usuario: tipo,
        rol,
      }
      for (const campo of [
        'documento_identidad',
        'telefono',
        'cargo',
        'entidad_externa',
      ]) {
        const valor = valorFormulario(form, campo)
        if (valor) datos[campo] = valor
      }
      guardar.mutate(datos)
      return
    }

    const cambios: Record<string, unknown> = {}
    const campos: Array<[string, string | null]> = [
      ['correo', usuario.correo],
      ['nombre_completo', usuario.nombre_completo],
      ['documento_identidad', usuario.documento_identidad],
      ['telefono', usuario.telefono],
      ['cargo', usuario.cargo],
      ['entidad_externa', usuario.entidad_externa],
    ]
    for (const [campo, original] of campos) {
      const valor = valorFormulario(form, campo)
      const normalizado = campo === 'correo' || campo === 'nombre_completo' ? valor : valor || null
      if (normalizado !== original) cambios[campo] = normalizado
    }
    if (contrasena) cambios.contrasena = contrasena
    if (Object.keys(cambios).length === 0) return
    guardar.mutate(cambios)
  }

  const error = guardar.error ?? cambiarRol.error ?? cambiarEstado.error
  const pendiente = guardar.isPending || cambiarRol.isPending || cambiarEstado.isPending
  const puedeEditar = !usuario || puede('usuarios.editar')

  return (
    <dialog ref={dialogo} className="modal" onClose={onCerrar} aria-labelledby="usuario-modal-titulo">
      <form onSubmit={enviar}>
        <div className="modal-header">
          <div>
            <h2 id="usuario-modal-titulo">{usuario ? 'Gestionar usuario' : 'Nuevo usuario'}</h2>
            {usuario && <p className="texto-secundario">{usuario.correo}</p>}
          </div>
          <button
            type="button"
            className="btn-icon"
            aria-label="Cerrar"
            onClick={() => dialogo.current?.close()}
          >
            ×
          </button>
        </div>

        {error && (
          <p className="alert-error" role="alert">
            {texto(error)}
          </p>
        )}

        <section className="modal-section">
          <h3>{usuario ? 'Datos generales' : 'Información del usuario'}</h3>
          <div className="form-grid">
            <div className="form-group form-span-2">
              <label className="form-label" htmlFor="usuario-nombre">
                Nombre completo
              </label>
              <input
                id="usuario-nombre"
                name="nombre_completo"
                className="form-control"
                defaultValue={usuario?.nombre_completo}
                required
                disabled={!puedeEditar}
                autoFocus
              />
            </div>
            <div className="form-group form-span-2">
              <label className="form-label" htmlFor="usuario-correo">
                Correo
              </label>
              <input
                id="usuario-correo"
                name="correo"
                type="email"
                className="form-control"
                defaultValue={usuario?.correo}
                required
                disabled={!puedeEditar}
                autoComplete="username"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="usuario-documento">
                Documento
              </label>
              <input
                id="usuario-documento"
                name="documento_identidad"
                className="form-control"
                defaultValue={usuario?.documento_identidad ?? ''}
                disabled={!puedeEditar}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="usuario-telefono">
                Teléfono
              </label>
              <input
                id="usuario-telefono"
                name="telefono"
                className="form-control"
                defaultValue={usuario?.telefono ?? ''}
                disabled={!puedeEditar}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="usuario-cargo">
                Cargo
              </label>
              <input
                id="usuario-cargo"
                name="cargo"
                className="form-control"
                defaultValue={usuario?.cargo ?? ''}
                disabled={!puedeEditar}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="usuario-entidad">
                Entidad externa
              </label>
              <input
                id="usuario-entidad"
                name="entidad_externa"
                className="form-control"
                defaultValue={usuario?.entidad_externa ?? ''}
                disabled={!puedeEditar}
              />
            </div>
            <div className="form-group form-span-2">
              <label className="form-label" htmlFor="usuario-contrasena">
                {usuario ? 'Nueva contraseña' : 'Contraseña'}
              </label>
              <input
                id="usuario-contrasena"
                name="contrasena"
                type="password"
                className="form-control"
                minLength={8}
                required={!usuario}
                disabled={!puedeEditar}
                autoComplete="new-password"
                placeholder={usuario ? 'Vacío para conservar la actual' : 'Mínimo 8 caracteres'}
              />
            </div>
          </div>

          {!usuario ? (
            <div className="form-grid">
              <Select
                id="usuario-tipo"
                label="Tipo de usuario"
                value={tipo}
                opciones={OPCIONES_TIPO}
                onChange={(evento) => cambiarTipo(evento.target.value as TipoUsuario)}
              />
              <Select
                id="usuario-rol"
                label="Rol"
                value={rol}
                opciones={opcionesRol(tipo)}
                onChange={(evento) => setRol(evento.target.value as CodigoRol)}
              />
            </div>
          ) : (
            <p className="dato-solo-lectura">
              Tipo de usuario: <strong>{etiquetaTipo(usuario.tipo_usuario)}</strong>
            </p>
          )}

          {puedeEditar && (
            <button type="submit" className="btn btn-primary" disabled={pendiente}>
              {guardar.isPending ? 'Guardando…' : usuario ? 'Guardar datos' : 'Crear usuario'}
            </button>
          )}
        </section>

        {usuario && puede('usuarios.cambiar_rol') && (
          <section className="modal-section">
            <h3>Cambiar rol</h3>
            <Select
              id="usuario-cambiar-rol"
              label="Rol asignado"
              value={rol}
              opciones={opcionesRol(usuario.tipo_usuario)}
              disabled={esPropio || pendiente}
              ayuda={esPropio ? 'No puede cambiar su propio rol.' : undefined}
              onChange={(evento) => setRol(evento.target.value as CodigoRol)}
            />
            <button
              type="button"
              className="btn btn-outline"
              disabled={esPropio || pendiente || rol === usuario.rol.codigo}
              onClick={() => cambiarRol.mutate(rol)}
            >
              {cambiarRol.isPending ? 'Actualizando…' : 'Actualizar rol'}
            </button>
          </section>
        )}

        {usuario && puede('usuarios.cambiar_estado') && (
          <section className="modal-section">
            <h3>Estado de acceso</h3>
            <p className="texto-secundario">
              El usuario está {usuario.activo ? 'activo' : 'inactivo'}.
            </p>
            <button
              type="button"
              className={usuario.activo ? 'btn btn-danger' : 'btn btn-primary'}
              disabled={(esPropio && usuario.activo) || pendiente}
              onClick={() => cambiarEstado.mutate(!usuario.activo)}
            >
              {cambiarEstado.isPending
                ? 'Actualizando…'
                : usuario.activo
                  ? 'Desactivar usuario'
                  : 'Activar usuario'}
            </button>
            {esPropio && usuario.activo && <small>No puede desactivar su propia cuenta.</small>}
          </section>
        )}

        <div className="modal-acciones">
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => dialogo.current?.close()}
            disabled={pendiente}
          >
            Cerrar
          </button>
        </div>
      </form>
    </dialog>
  )
}

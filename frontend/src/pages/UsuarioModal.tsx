import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import {
  CLAVE_SESION,
  type CodigoRol,
  useSesion,
} from '../auth/sesion'
import { Select } from '../components/Select'
import {
  type Usuario,
  esRolSolicitante,
  etiquetaTipo,
  opcionesRol,
} from './usuarios'

interface Props {
  usuario?: Usuario
  onGuardado: () => Promise<unknown>
  onCerrar: () => void
}

type CampoCreacion = 'correo' | 'contrasena' | 'nombre_completo' | 'rol'
type ErroresCreacion = Partial<Record<CampoCreacion, string>>

const OPCIONES_ROL_INTERNO = [
  { value: '', label: 'Seleccione un rol' },
  ...opcionesRol('INTERNO'),
]

const PATRON_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

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
  const notify = useNotifications()
  const { sesion, puede } = useSesion()
  const esPropio = usuario?.id === sesion?.id
  const esSolicitante = usuario ? esRolSolicitante(usuario.rol.codigo) : false
  const esSolicitanteInterno = esSolicitante && usuario?.tipo_usuario === 'INTERNO'
  const [rol, setRol] = useState<CodigoRol | ''>(usuario?.rol.codigo ?? '')
  const [erroresCreacion, setErroresCreacion] = useState<ErroresCreacion>({})

  async function completar(mensaje: string, afectaSesion = false) {
    await onGuardado()
    dialogo.current?.close()
    notify({ type: 'success', message: mensaje })
    if (afectaSesion) {
      await queryClient.invalidateQueries({ queryKey: CLAVE_SESION })
    }
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
    onError: (error) => notify({ type: 'error', message: texto(error) }),
  })

  const cambiarRol = useMutation({
    mutationFn: (codigo: CodigoRol) =>
      apiFetch<Usuario>(`/usuarios/${usuario?.id}/rol`, {
        method: 'PATCH',
        body: JSON.stringify({ rol: codigo }),
      }),
    onSuccess: () => completar('Rol actualizado.'),
    onError: (error) => notify({ type: 'error', message: texto(error) }),
  })

  const cambiarEstado = useMutation({
    mutationFn: (activo: boolean) =>
      apiFetch<Usuario>(`/usuarios/${usuario?.id}/estado`, {
        method: 'PATCH',
        body: JSON.stringify({ activo }),
      }),
    onSuccess: () => completar(usuario?.activo ? 'Usuario desactivado.' : 'Usuario activado.'),
    onError: (error) => notify({ type: 'error', message: texto(error) }),
  })

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  function validarCreacion(form: FormData, contrasena: string): ErroresCreacion {
    const errores: ErroresCreacion = {}
    const correo = valorFormulario(form, 'correo')
    if (!correo) errores.correo = 'El correo es obligatorio.'
    else if (!PATRON_CORREO.test(correo)) errores.correo = 'Ingrese un correo válido.'
    if (!valorFormulario(form, 'nombre_completo')) {
      errores.nombre_completo = 'El nombre completo es obligatorio.'
    }
    if (!contrasena) errores.contrasena = 'La contraseña es obligatoria.'
    else if (contrasena.length < 8) {
      errores.contrasena = 'La contraseña debe tener al menos 8 caracteres.'
    }
    if (!rol) errores.rol = 'Seleccione un rol.'
    return errores
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const contrasena = String(form.get('contrasena') ?? '')

    if (!usuario) {
      if (pendiente) return
      const errores = validarCreacion(form, contrasena)
      setErroresCreacion(errores)
      if (Object.keys(errores).length > 0 || !rol) return
      const datos: Record<string, unknown> = {
        correo: valorFormulario(form, 'correo'),
        contrasena,
        nombre_completo: valorFormulario(form, 'nombre_completo'),
        tipo_usuario: 'INTERNO',
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
      ['nombre_completo', usuario.nombre_completo],
      ['telefono', usuario.telefono],
      ['cargo', usuario.cargo],
    ]
    if (!esSolicitanteInterno) {
      campos.push(
        ['documento_identidad', usuario.documento_identidad],
        ['entidad_externa', usuario.entidad_externa],
      )
    }
    if (!esSolicitante) campos.unshift(['correo', usuario.correo])
    for (const [campo, original] of campos) {
      const valor = valorFormulario(form, campo)
      const normalizado = campo === 'correo' || campo === 'nombre_completo' ? valor : valor || null
      if (normalizado !== original) cambios[campo] = normalizado
    }
    if (!esSolicitante && contrasena) cambios.contrasena = contrasena
    if (Object.keys(cambios).length === 0) return
    guardar.mutate(cambios)
  }

  const pendiente = guardar.isPending || cambiarRol.isPending || cambiarEstado.isPending
  const puedeEditar = !usuario || puede('usuarios.editar')

  return (
    <dialog ref={dialogo} className="modal" onClose={onCerrar} aria-labelledby="usuario-modal-titulo">
      <form onSubmit={enviar} noValidate>
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
                className={`form-control ${erroresCreacion.nombre_completo ? 'is-invalid' : ''}`}
                defaultValue={usuario?.nombre_completo}
                required
                disabled={!puedeEditar}
                autoFocus
                aria-invalid={Boolean(erroresCreacion.nombre_completo)}
                aria-describedby={
                  erroresCreacion.nombre_completo ? 'usuario-nombre-error' : undefined
                }
                onChange={() =>
                  setErroresCreacion((actuales) => ({
                    ...actuales,
                    nombre_completo: undefined,
                  }))
                }
              />
              {erroresCreacion.nombre_completo && (
                <small id="usuario-nombre-error" className="form-error">
                  {erroresCreacion.nombre_completo}
                </small>
              )}
            </div>
            <div className="form-group form-span-2">
              <label className="form-label" htmlFor="usuario-correo">
                Correo
              </label>
              <input
                id="usuario-correo"
                name="correo"
                type="email"
                className={`form-control ${erroresCreacion.correo ? 'is-invalid' : ''}`}
                defaultValue={usuario?.correo}
                required
                disabled={!puedeEditar || esSolicitante}
                autoComplete="username"
                aria-invalid={Boolean(erroresCreacion.correo)}
                aria-describedby={erroresCreacion.correo ? 'usuario-correo-error' : undefined}
                onChange={() =>
                  setErroresCreacion((actuales) => ({ ...actuales, correo: undefined }))
                }
              />
              {erroresCreacion.correo && (
                <small id="usuario-correo-error" className="form-error">
                  {erroresCreacion.correo}
                </small>
              )}
              {esSolicitante && (
                <small>El correo del solicitante se conserva según su autorregistro.</small>
              )}
            </div>
            {!esSolicitanteInterno && (
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
            )}
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
            {!esSolicitanteInterno && (
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
            )}
            {!esSolicitante && (
              <div className="form-group form-span-2">
                <label className="form-label" htmlFor="usuario-contrasena">
                  {usuario ? 'Nueva contraseña' : 'Contraseña'}
                </label>
                <input
                  id="usuario-contrasena"
                  name="contrasena"
                  type="password"
                  className={`form-control ${erroresCreacion.contrasena ? 'is-invalid' : ''}`}
                  minLength={8}
                  required={!usuario}
                  disabled={!puedeEditar}
                  autoComplete="new-password"
                  placeholder={usuario ? 'Vacío para conservar la actual' : 'Mínimo 8 caracteres'}
                  aria-invalid={Boolean(erroresCreacion.contrasena)}
                  aria-describedby={
                    erroresCreacion.contrasena ? 'usuario-contrasena-error' : undefined
                  }
                  onChange={() =>
                    setErroresCreacion((actuales) => ({
                      ...actuales,
                      contrasena: undefined,
                    }))
                  }
                />
                {erroresCreacion.contrasena && (
                  <small id="usuario-contrasena-error" className="form-error">
                    {erroresCreacion.contrasena}
                  </small>
                )}
              </div>
            )}
          </div>

          {!usuario ? (
            <div className="form-grid">
              <div>
                <Select
                  id="usuario-rol"
                  name="rol"
                  label="Rol"
                  value={rol}
                  opciones={OPCIONES_ROL_INTERNO}
                  required
                  aria-invalid={Boolean(erroresCreacion.rol)}
                  aria-describedby={erroresCreacion.rol ? 'usuario-rol-error' : undefined}
                  className={erroresCreacion.rol ? 'is-invalid' : undefined}
                  onChange={(evento) => {
                    setRol(evento.target.value as CodigoRol | '')
                    setErroresCreacion((actuales) => ({ ...actuales, rol: undefined }))
                  }}
                />
                {erroresCreacion.rol && (
                  <small id="usuario-rol-error" className="form-error">
                    {erroresCreacion.rol}
                  </small>
                )}
              </div>
            </div>
          ) : (
            <div className="dato-solo-lectura">
              <p>
                Tipo de usuario: <strong>{etiquetaTipo(usuario.tipo_usuario)}</strong>
              </p>
              <p>
                Rol actual: <strong>{usuario.rol.nombre}</strong>
              </p>
            </div>
          )}

          {puedeEditar && (
            <button type="submit" className="btn btn-primary" disabled={pendiente}>
              {guardar.isPending ? 'Guardando…' : usuario ? 'Guardar datos' : 'Crear usuario'}
            </button>
          )}
        </section>

        {usuario && !esSolicitante && puede('usuarios.cambiar_rol') && (
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
              onClick={() => rol && cambiarRol.mutate(rol)}
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

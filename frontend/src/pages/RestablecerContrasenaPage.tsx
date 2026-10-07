import { useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { PasswordInput } from '../components/PasswordInput'
import {
  PASSWORD_POLICY_MESSAGE,
  passwordPolicyError,
} from '../security/passwordPolicy'

interface MensajePublico {
  message: string
}

function codigoError(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object') {
    return undefined
  }
  if ('codigo' in error.detail && typeof error.detail.codigo === 'string') {
    return error.detail.codigo
  }
  return undefined
}

function esErrorEnlace(codigo: string | undefined): boolean {
  return (
    codigo === 'ENLACE_INVALIDO' ||
    codigo === 'ENLACE_EXPIRADO' ||
    codigo === 'ENLACE_NO_DISPONIBLE'
  )
}

export function RestablecerContrasenaPage() {
  const [parametros] = useSearchParams()
  const token = parametros.get('token')?.trim() ?? ''
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null)
  const validacion = useQuery({
    queryKey: ['validar-recuperacion-contrasena', token],
    queryFn: () =>
      apiFetch<MensajePublico>('/auth/validar-recuperacion-contrasena', {
        method: 'POST',
        body: JSON.stringify({ token }),
      }),
    enabled: token.length > 0,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
  })
  const restablecimiento = useMutation({
    mutationFn: (datos: { nueva_contrasena: string; confirmacion_contrasena: string }) =>
      apiFetch<MensajePublico>('/auth/restablecer-contrasena', {
        method: 'POST',
        body: JSON.stringify({ token, ...datos }),
      }),
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    const nuevaContrasena = String(datos.get('nueva_contrasena') ?? '')
    const confirmacion = String(datos.get('confirmacion_contrasena') ?? '')
    const errorPolitica = passwordPolicyError(nuevaContrasena)
    if (errorPolitica) {
      setErrorFormulario(errorPolitica)
      return
    }
    if (nuevaContrasena !== confirmacion) {
      setErrorFormulario('Las contraseñas no coinciden.')
      return
    }
    setErrorFormulario(null)
    restablecimiento.mutate({
      nueva_contrasena: nuevaContrasena,
      confirmacion_contrasena: confirmacion,
    })
  }

  if (!token) {
    return <EstadoEnlace titulo="Enlace inválido" mensaje="El enlace no contiene un token válido." />
  }

  if (validacion.isPending || validacion.isFetching) {
    return (
      <main className="login-page">
        <section className="card card-auth">
          <div className="login-brand">ORI Manager</div>
          <h1>Validando enlace</h1>
          <p className="texto-secundario" role="status">
            Estamos comprobando que el enlace de recuperación siga disponible.
          </p>
          <div className="verificacion-cargando" aria-hidden="true" />
        </section>
      </main>
    )
  }

  if (validacion.isError) {
    const codigo = codigoError(validacion.error)
    const expirado = codigo === 'ENLACE_EXPIRADO'
    return (
      <EstadoEnlace
        titulo={expirado ? 'Enlace expirado' : codigo === 'ENLACE_NO_DISPONIBLE' ? 'Enlace no disponible' : 'Enlace inválido'}
        mensaje={
          expirado
            ? 'El enlace venció. Solicite uno nuevo para restablecer su contraseña.'
            : codigo === 'ENLACE_NO_DISPONIBLE'
              ? 'El enlace ya fue utilizado o dejó de estar disponible.'
              : 'El enlace de recuperación no es válido.'
        }
      />
    )
  }

  if (restablecimiento.isSuccess) {
    return (
      <main className="login-page">
        <section className="card card-auth">
          <div className="login-brand">ORI Manager</div>
          <h1>Contraseña actualizada</h1>
          <p className="alert-success" role="status">
            Su contraseña fue actualizada. Ya puede iniciar sesión.
          </p>
          <Link className="btn btn-primary btn-block" to="/login">Iniciar sesión</Link>
        </section>
      </main>
    )
  }

  const codigo = codigoError(restablecimiento.error)
  if (esErrorEnlace(codigo)) {
    const expirado = codigo === 'ENLACE_EXPIRADO'
    return (
      <EstadoEnlace
        titulo={expirado ? 'Enlace expirado' : codigo === 'ENLACE_INVALIDO' ? 'Enlace inválido' : 'Enlace no disponible'}
        mensaje={
          expirado
            ? 'El enlace venció. Solicite uno nuevo para restablecer su contraseña.'
            : 'El enlace es inválido, ya fue utilizado o dejó de estar disponible.'
        }
      />
    )
  }

  const mensajeError =
    errorFormulario ??
    (restablecimiento.error instanceof ApiError
      ? restablecimiento.error.message
      : 'No fue posible actualizar la contraseña.')

  function limpiarErrorFormulario() {
    setErrorFormulario(null)
    if (restablecimiento.isError) restablecimiento.reset()
  }

  return (
    <main className="login-page">
      <section className="card card-auth">
        <div className="login-brand">ORI Manager</div>
        <h1>Nueva contraseña</h1>
        <p className="texto-secundario">Defina la nueva credencial con la que accederá a su cuenta.</p>
        <form onSubmit={enviar}>
          {(errorFormulario || restablecimiento.isError) && (
            <p className="alert-error" role="alert">
              {mensajeError}
            </p>
          )}
          <div className="form-group">
            <PasswordInput
              id="nueva-contrasena"
              label="Nueva contraseña"
              name="nueva_contrasena"
              required
              autoComplete="new-password"
              autoFocus
              placeholder="Cree una contraseña segura"
              aria-describedby="restablecer-politica-contrasena"
              onChange={limpiarErrorFormulario}
            />
            <small id="restablecer-politica-contrasena" className="form-help">
              {PASSWORD_POLICY_MESSAGE}
            </small>
          </div>
          <div className="form-group">
            <PasswordInput
              id="confirmacion-contrasena"
              label="Confirmar contraseña"
              name="confirmacion_contrasena"
              required
              autoComplete="new-password"
              placeholder="Repita la nueva contraseña"
              onChange={limpiarErrorFormulario}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={restablecimiento.isPending}
          >
            {restablecimiento.isPending ? 'Actualizando…' : 'Actualizar contraseña'}
          </button>
        </form>
      </section>
    </main>
  )
}

function EstadoEnlace({ titulo, mensaje }: { titulo: string; mensaje: string }) {
  return (
    <main className="login-page">
      <section className="card card-auth">
        <div className="login-brand">ORI Manager</div>
        <h1>{titulo}</h1>
        <p className="texto-secundario" role="alert">{mensaje}</p>
        <Link className="btn btn-primary btn-block" to="/recuperar-contrasena">
          Solicitar un nuevo enlace
        </Link>
        <p className="registro-login"><Link to="/login">Volver a iniciar sesión</Link></p>
      </section>
    </main>
  )
}

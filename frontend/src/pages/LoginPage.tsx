import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { CLAVE_SESION, useSesion } from '../auth/sesion'

interface Credenciales {
  correo: string
  contrasena: string
}

export function LoginPage() {
  const { sesion, cargando, error: errorSesion } = useSesion()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const login = useMutation({
    mutationFn: (credenciales: Credenciales) =>
      apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify(credenciales),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: CLAVE_SESION })
      await queryClient.refetchQueries({ queryKey: CLAVE_SESION })
      navigate('/', { replace: true })
    },
  })

  if (cargando) return <p className="estado-pagina">Validando sesión…</p>
  if (errorSesion) {
    return (
      <main className="login-page">
        <section className="card estado-vacio">
          <h1>No se pudo conectar</h1>
          <p>{errorSesion.message}</p>
        </section>
      </main>
    )
  }
  if (sesion) return <Navigate to="/" replace />

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    login.mutate({
      correo: String(datos.get('correo') ?? '').trim(),
      contrasena: String(datos.get('contrasena') ?? ''),
    })
  }

  const mensajeError =
    login.error instanceof ApiError ? login.error.message : 'No fue posible iniciar sesión.'

  return (
    <main className="login-page">
      <section className="card card-auth">
        <div className="login-brand">ORI Manager</div>
        <h1>Iniciar sesión</h1>
        <p className="texto-secundario">Ingrese con su cuenta institucional.</p>

        <form onSubmit={enviar}>
          {login.isError && (
            <p className="alert-error" role="alert">
              {mensajeError}
            </p>
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="correo">
              Correo
            </label>
            <input
              id="correo"
              name="correo"
              type="email"
              className="form-control"
              required
              autoComplete="username"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="contrasena">
              Contraseña
            </label>
            <input
              id="contrasena"
              name="contrasena"
              type="password"
              className="form-control"
              required
              autoComplete="current-password"
            />
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={login.isPending}>
            {login.isPending ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>
        <p className="registro-login">
          ¿No tiene cuenta? <Link to="/registro">Crear cuenta</Link>
        </p>
      </section>
    </main>
  )
}

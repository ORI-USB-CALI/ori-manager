import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiFetch } from '../app/api'
import { CLAVE_SESION } from '../auth/sesion'

// Login mínimo para poder verificar roles; la experiencia completa pertenece a la HU de autenticación.
export function LoginPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const login = useMutation({
    mutationFn: (credenciales: { email: string; password: string }) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(credenciales) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: CLAVE_SESION })
      navigate('/')
    },
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    login.mutate({ email: String(datos.get('email')), password: String(datos.get('password')) })
  }

  return (
    <section className="card card-auth">
      <h1>Iniciar sesión</h1>
      <form onSubmit={enviar}>
        {login.isError && (
          <p className="alert-error" role="alert">
            {login.error.message}
          </p>
        )}
        <div className="form-group">
          <label className="form-label" htmlFor="email">
            Correo
          </label>
          <input
            id="email"
            name="email"
            type="email"
            className={`form-control${login.isError ? ' is-invalid' : ''}`}
            required
            autoComplete="username"
          />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            name="password"
            type="password"
            className={`form-control${login.isError ? ' is-invalid' : ''}`}
            required
            autoComplete="current-password"
          />
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={login.isPending}>
          {login.isPending ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </section>
  )
}

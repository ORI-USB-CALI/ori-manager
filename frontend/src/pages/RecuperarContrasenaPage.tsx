import { useMutation } from '@tanstack/react-query'
import { type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'

interface MensajePublico {
  message: string
}

const MENSAJE_PUBLICO =
  'Si existe una cuenta habilitada asociada a este correo, revisa tu bandeja para continuar.'

export function RecuperarContrasenaPage() {
  const recuperacion = useMutation({
    mutationFn: (correo: string) =>
      apiFetch<MensajePublico>('/auth/recuperar-contrasena', {
        method: 'POST',
        body: JSON.stringify({ correo }),
      }),
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const datos = new FormData(evento.currentTarget)
    recuperacion.mutate(String(datos.get('correo') ?? '').trim())
  }

  return (
    <main className="login-page">
      <section className="card card-auth">
        <div className="login-brand">ORI Manager</div>
        <h1>Recuperar contraseña</h1>
        <p className="texto-secundario">
          Recibirá instrucciones para continuar con la recuperación de acceso.
        </p>

        {recuperacion.isSuccess ? (
          <p className="alert-success" role="status">{MENSAJE_PUBLICO}</p>
        ) : (
          <form onSubmit={enviar}>
            {recuperacion.isError && (
              <p className="alert-error" role="alert">
                No fue posible procesar la solicitud. Intente nuevamente.
              </p>
            )}
            <div className="form-group">
              <label className="form-label" htmlFor="recuperacion-correo">Correo</label>
              <input
                id="recuperacion-correo"
                name="correo"
                type="email"
                className="form-control"
                required
                autoComplete="email"
                autoFocus
                placeholder="Correo asociado a su cuenta"
              />
            </div>
            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={recuperacion.isPending}
            >
              {recuperacion.isPending ? 'Enviando…' : 'Enviar instrucciones'}
            </button>
          </form>
        )}
        <p className="registro-login">
          <Link to="/login">Volver a iniciar sesión</Link>
        </p>
      </section>
    </main>
  )
}

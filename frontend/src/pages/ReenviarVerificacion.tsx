import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { ApiError, apiFetch } from '../app/api'

interface MensajePublico {
  message: string
}

interface ReenviarVerificacionProps {
  correoInicial?: string
}

export function ReenviarVerificacion({ correoInicial = '' }: ReenviarVerificacionProps) {
  const [correo, setCorreo] = useState(correoInicial)
  const reenvio = useMutation({
    mutationFn: () =>
      apiFetch<MensajePublico>('/auth/reenviar-verificacion', {
        method: 'POST',
        body: JSON.stringify({ correo: correo.trim() }),
      }),
  })

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    reenvio.mutate()
  }

  const mensajeError =
    reenvio.error instanceof ApiError
      ? reenvio.error.message
      : 'No fue posible procesar la solicitud.'

  return (
    <form className="reenvio-verificacion" onSubmit={enviar}>
      <label className="form-group" htmlFor="correo-reenvio">
        <span className="form-label">Correo de la cuenta</span>
        <input
          id="correo-reenvio"
          className="form-control"
          type="email"
          value={correo}
          onChange={(evento) => setCorreo(evento.target.value)}
          required
          autoComplete="email"
          placeholder="Correo con el que creó su cuenta"
        />
      </label>
      {reenvio.isSuccess && (
        <p className="alert-success" role="status">{reenvio.data.message}</p>
      )}
      {reenvio.isError && <p className="alert-error" role="alert">{mensajeError}</p>}
      <button className="btn btn-outline btn-block" type="submit" disabled={reenvio.isPending}>
        {reenvio.isPending ? 'Enviando…' : 'Reenviar correo de verificación'}
      </button>
    </form>
  )
}

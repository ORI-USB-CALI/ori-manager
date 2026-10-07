import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { ReenviarVerificacion } from './ReenviarVerificacion'

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

export function VerificarCorreoPage() {
  const [parametros] = useSearchParams()
  const token = parametros.get('token')?.trim() ?? ''
  const verificacion = useQuery({
    queryKey: ['verificar-correo', token],
    queryFn: () =>
      apiFetch<MensajePublico>('/auth/verificar-correo', {
        method: 'POST',
        body: JSON.stringify({ token }),
      }),
    enabled: token.length > 0,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
  })

  let titulo = 'Verificando correo'
  let mensaje = 'Estamos validando su enlace de verificación.'
  if (!token) {
    titulo = 'Enlace inválido'
    mensaje = 'El enlace no contiene un token de verificación válido.'
  } else if (verificacion.isSuccess) {
    titulo = 'Correo verificado'
    mensaje = 'Su cuenta quedó verificada. Ya puede iniciar sesión.'
  } else if (verificacion.isError) {
    const codigo = codigoError(verificacion.error)
    titulo = codigo === 'ENLACE_EXPIRADO' ? 'Enlace expirado' : 'Enlace no disponible'
    mensaje =
      codigo === 'ENLACE_EXPIRADO'
        ? 'El enlace venció. Solicite uno nuevo para verificar su cuenta.'
        : 'El enlace es inválido o ya fue utilizado.'
  }

  const mostrarReenvio = !token || verificacion.isError

  return (
    <main className="login-page">
      <section className="card card-auth">
        <div className="login-brand">ORI Manager</div>
        <h1>{titulo}</h1>
        <p
          className={verificacion.isSuccess ? 'alert-success' : 'texto-secundario'}
          role="status"
        >
          {mensaje}
        </p>
        {verificacion.isFetching && <div className="verificacion-cargando" aria-hidden="true" />}
        {mostrarReenvio && <ReenviarVerificacion />}
        {!verificacion.isFetching && (
          <Link className="btn btn-primary btn-block" to="/login">
            Volver a iniciar sesión
          </Link>
        )}
      </section>
    </main>
  )
}

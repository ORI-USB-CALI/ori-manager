import { useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'

type TipoSolicitante = 'INTERNO' | 'EXTERNO'

interface UnidadRegistro {
  id: number
  nombre: string
  tipo: 'FACULTAD' | 'PROGRAMA' | 'UNIDAD_ADMINISTRATIVA'
}

interface RespuestaRegistro {
  estado: 'VERIFICACION_PENDIENTE'
  mensaje: string
  tipo_usuario: TipoSolicitante
}

const DOMINIOS_INSTITUCIONALES = new Set([
  'correo.usbcali.edu.co',
  'usbcali.edu.co',
])

function clasificar(correo: string): TipoSolicitante {
  const dominio = correo.trim().toLowerCase().split('@').at(-1) ?? ''
  return DOMINIOS_INSTITUCIONALES.has(dominio) ? 'INTERNO' : 'EXTERNO'
}

export function RegistroPage() {
  const [correo, setCorreo] = useState('')
  const [tipo, setTipo] = useState<TipoSolicitante | null>(null)
  const unidades = useQuery({
    queryKey: ['registro', 'unidades'],
    queryFn: () => apiFetch<UnidadRegistro[]>('/auth/registro/unidades'),
    enabled: tipo === 'INTERNO',
    retry: false,
  })
  const registro = useMutation({
    mutationFn: (datos: Record<string, unknown>) =>
      apiFetch<RespuestaRegistro>('/auth/registro', {
        method: 'POST',
        body: JSON.stringify(datos),
      }),
  })

  function continuar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setTipo(clasificar(correo))
    registro.reset()
  }

  function registrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const form = new FormData(evento.currentTarget)
    const datos: Record<string, unknown> = {
      correo: correo.trim(),
      contrasena: String(form.get('contrasena') ?? ''),
      confirmacion_contrasena: String(form.get('confirmacion_contrasena') ?? ''),
      nombre_completo: String(form.get('nombre_completo') ?? '').trim(),
      cargo: String(form.get('cargo') ?? '').trim(),
    }
    if (tipo === 'INTERNO') {
      datos.unidad_organizacional_id = Number(form.get('unidad_organizacional_id'))
    } else {
      datos.documento_identidad = String(form.get('documento_identidad') ?? '').trim()
      datos.entidad_externa = String(form.get('entidad_externa') ?? '').trim()
    }
    registro.mutate(datos)
  }

  const mensajeError =
    registro.error instanceof ApiError
      ? registro.error.message
      : 'No fue posible crear la cuenta.'

  if (registro.data) {
    return (
      <main className="login-page">
        <section className="card card-auth">
          <div className="login-brand">ORI Manager</div>
          <h1>Cuenta creada</h1>
          <p className="alert-success" role="status">
            {registro.data.mensaje}
          </p>
          <p className="texto-secundario">
            El envío del correo de verificación estará disponible próximamente.
          </p>
          <Link className="btn btn-primary btn-block" to="/login">
            Volver a iniciar sesión
          </Link>
        </section>
      </main>
    )
  }

  return (
    <main className="login-page">
      <section className="card card-auth card-registro">
        <div className="login-brand">ORI Manager</div>
        <h1>Crear cuenta</h1>
        <p className="texto-secundario">
          El tipo de solicitante se determina automáticamente con su correo.
        </p>

        {tipo === null ? (
          <form onSubmit={continuar}>
            <div className="form-group">
              <label className="form-label" htmlFor="registro-correo">Correo</label>
              <input
                id="registro-correo"
                className="form-control"
                type="email"
                value={correo}
                onChange={(evento) => setCorreo(evento.target.value)}
                required
                autoComplete="email"
                autoFocus
              />
            </div>
            <button className="btn btn-primary btn-block" type="submit">
              Continuar
            </button>
          </form>
        ) : (
          <form onSubmit={registrar}>
            <p className="alert-success" role="status">
              Solicitante {tipo === 'INTERNO' ? 'interno' : 'externo'} · {correo}
            </p>
            {registro.isError && <p className="alert-error" role="alert">{mensajeError}</p>}
            <div className="form-grid">
              <label className="form-group form-span-2">
                <span className="form-label">Nombre completo</span>
                <input className="form-control" name="nombre_completo" required autoFocus />
              </label>
              <label className="form-group form-span-2">
                <span className="form-label">Cargo</span>
                <input className="form-control" name="cargo" required />
              </label>
              {tipo === 'INTERNO' ? (
                <label className="form-group form-span-2">
                  <span className="form-label">Unidad organizacional</span>
                  <select
                    className="form-control select"
                    name="unidad_organizacional_id"
                    required
                    disabled={unidades.isPending || unidades.isError}
                  >
                    <option value="">Seleccione</option>
                    {unidades.data?.map((unidad) => (
                      <option key={unidad.id} value={unidad.id}>
                        {unidad.nombre} · {unidad.tipo.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                  {unidades.isError && (
                    <small className="form-error">No fue posible cargar las unidades.</small>
                  )}
                </label>
              ) : (
                <>
                  <label className="form-group">
                    <span className="form-label">Documento de identidad</span>
                    <input className="form-control" name="documento_identidad" required />
                  </label>
                  <label className="form-group">
                    <span className="form-label">Entidad externa</span>
                    <input className="form-control" name="entidad_externa" required />
                  </label>
                </>
              )}
              <label className="form-group">
                <span className="form-label">Contraseña</span>
                <input
                  className="form-control"
                  name="contrasena"
                  type="password"
                  minLength={8}
                  required
                  autoComplete="new-password"
                />
              </label>
              <label className="form-group">
                <span className="form-label">Confirmar contraseña</span>
                <input
                  className="form-control"
                  name="confirmacion_contrasena"
                  type="password"
                  minLength={8}
                  required
                  autoComplete="new-password"
                />
              </label>
            </div>
            <p className="texto-secundario registro-aviso">
              Después del registro deberá verificar su correo antes de iniciar sesión.
            </p>
            <div className="registro-acciones">
              <button className="btn btn-outline" type="button" onClick={() => setTipo(null)}>
                Cambiar correo
              </button>
              <button className="btn btn-primary" type="submit" disabled={registro.isPending}>
                {registro.isPending ? 'Creando…' : 'Crear cuenta'}
              </button>
            </div>
          </form>
        )}
        <p className="registro-login">¿Ya tiene cuenta? <Link to="/login">Iniciar sesión</Link></p>
      </section>
    </main>
  )
}

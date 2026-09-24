import { useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { ReenviarVerificacion } from './ReenviarVerificacion'

type TipoSolicitante = 'INTERNO' | 'EXTERNO'
type SiguientePaso = 'VERIFICAR_CORREO' | 'INICIAR_SESION'

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

function siguientePasoRegistro(error: unknown): SiguientePaso | null {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object') {
    return null
  }
  if (!('codigo' in error.detail) || error.detail.codigo !== 'CORREO_REGISTRADO') {
    return null
  }
  if (
    'siguiente_paso' in error.detail &&
    (error.detail.siguiente_paso === 'VERIFICAR_CORREO' ||
      error.detail.siguiente_paso === 'INICIAR_SESION')
  ) {
    return error.detail.siguiente_paso
  }
  return null
}

function clasificar(correo: string): TipoSolicitante {
  const dominio = correo.trim().toLowerCase().split('@').at(-1) ?? ''
  return DOMINIOS_INSTITUCIONALES.has(dominio) ? 'INTERNO' : 'EXTERNO'
}

export function RegistroPage() {
  const [correo, setCorreo] = useState('')
  const [tipo, setTipo] = useState<TipoSolicitante | null>(null)
  const [cuentaExistente, setCuentaExistente] = useState<SiguientePaso | null>(null)
  const [mostrarReenvio, setMostrarReenvio] = useState(false)
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
    onMutate: () => setCuentaExistente(null),
    onError: (error) => setCuentaExistente(siguientePasoRegistro(error)),
  })

  function continuar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setTipo(clasificar(correo))
    setCuentaExistente(null)
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

  if (cuentaExistente === 'VERIFICAR_CORREO') {
    return (
      <main className="login-page">
        <section className="card card-auth">
          <div className="login-brand">ORI Manager</div>
          <h1>Verificación pendiente</h1>
          <p className="alert-success" role="status">
            Tu cuenta ya fue creada y está pendiente de verificación.
          </p>
          <p className="correo-cuenta">{correo.trim()}</p>
          <ReenviarVerificacion correoInicial={correo} />
          <div className="acciones-cuenta-existente">
            <button className="btn btn-outline btn-block" type="button" onClick={() => {
              setCuentaExistente(null)
              setTipo(null)
              registro.reset()
            }}>
              Usar otro correo
            </button>
            <Link className="btn btn-primary btn-block" to="/login">
              Volver a iniciar sesión
            </Link>
          </div>
        </section>
      </main>
    )
  }

  if (cuentaExistente === 'INICIAR_SESION') {
    return (
      <main className="login-page">
        <section className="card card-auth">
          <div className="login-brand">ORI Manager</div>
          <h1>Cuenta existente</h1>
          <p className="alert-success" role="status">
            Ya existe una cuenta verificada con este correo.
          </p>
          <p className="correo-cuenta">{correo.trim()}</p>
          <div className="acciones-cuenta-existente">
            <Link className="btn btn-primary btn-block" to="/login">
              Iniciar sesión
            </Link>
            <button className="btn btn-outline btn-block" type="button" onClick={() => {
              setCuentaExistente(null)
              setTipo(null)
              registro.reset()
            }}>
              Usar otro correo
            </button>
          </div>
        </section>
      </main>
    )
  }

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
            Revisa tu correo para verificar tu cuenta. El enlace vence en 24 horas.
          </p>
          <ReenviarVerificacion correoInicial={correo} />
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
          Los dominios @correo.usbcali.edu.co y @usbcali.edu.co se clasifican como internos; los demás, como externos.
        </p>

        {tipo === null ? (
          <>
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
                  placeholder="Correo de acceso"
                />
              </div>
              <button className="btn btn-primary btn-block" type="submit">
                Continuar
              </button>
            </form>
            <div className="registro-reenvio-directo">
              <p className="texto-secundario">
                ¿Ya creaste tu cuenta y no recibiste el correo?
              </p>
              <button
                className="btn btn-outline btn-block"
                type="button"
                onClick={() => setMostrarReenvio((visible) => !visible)}
              >
                Reenviar correo de verificación
              </button>
              {mostrarReenvio && <ReenviarVerificacion correoInicial={correo} />}
            </div>
          </>
        ) : (
          <form onSubmit={registrar}>
            <p className="alert-success" role="status">
              Solicitante {tipo === 'INTERNO' ? 'interno' : 'externo'} · {correo}
            </p>
            {registro.isError && <p className="alert-error" role="alert">{mensajeError}</p>}
            <div className="form-grid">
              <label className="form-group form-span-2" htmlFor="registro-nombre">
                <span className="form-label">Nombre completo</span>
                <input id="registro-nombre" className="form-control" name="nombre_completo" required autoFocus placeholder="Nombre completo del solicitante" />
              </label>
              <label className="form-group form-span-2" htmlFor="registro-cargo">
                <span className="form-label">Cargo</span>
                <input id="registro-cargo" className="form-control" name="cargo" required placeholder="Cargo en la Universidad o entidad" />
              </label>
              {tipo === 'INTERNO' ? (
                <label className="form-group form-span-2" htmlFor="registro-unidad">
                  <span className="form-label">Unidad organizacional</span>
                  <select
                    id="registro-unidad"
                    className="form-control select"
                    name="unidad_organizacional_id"
                    required
                    disabled={unidades.isPending || unidades.isError}
                    aria-describedby={unidades.isError ? 'registro-unidad-error' : undefined}
                  >
                    <option value="">Seleccione una unidad organizacional</option>
                    {unidades.data?.map((unidad) => (
                      <option key={unidad.id} value={unidad.id}>
                        {unidad.nombre} · {unidad.tipo.replaceAll('_', ' ')}
                      </option>
                    ))}
                  </select>
                  {unidades.isError && (
                    <small id="registro-unidad-error" className="form-error">No fue posible cargar las unidades.</small>
                  )}
                </label>
              ) : (
                <>
                  <label className="form-group" htmlFor="registro-documento">
                    <span className="form-label">Documento de identidad</span>
                    <input id="registro-documento" className="form-control" name="documento_identidad" required placeholder="Documento del solicitante externo" />
                  </label>
                  <label className="form-group" htmlFor="registro-entidad">
                    <span className="form-label">Entidad externa</span>
                    <input id="registro-entidad" className="form-control" name="entidad_externa" required placeholder="Nombre de la organización externa" />
                  </label>
                </>
              )}
              <label className="form-group" htmlFor="registro-contrasena">
                <span className="form-label">Contraseña</span>
                <input
                  id="registro-contrasena"
                  className="form-control"
                  name="contrasena"
                  type="password"
                  minLength={8}
                  required
                  autoComplete="new-password"
                  placeholder="Mínimo 8 caracteres"
                />
              </label>
              <label className="form-group" htmlFor="registro-confirmacion">
                <span className="form-label">Confirmar contraseña</span>
                <input
                  id="registro-confirmacion"
                  className="form-control"
                  name="confirmacion_contrasena"
                  type="password"
                  minLength={8}
                  required
                  autoComplete="new-password"
                  placeholder="Repita la contraseña"
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

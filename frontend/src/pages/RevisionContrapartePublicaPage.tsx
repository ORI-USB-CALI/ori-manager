import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type ReactNode } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { ConvenioEditor } from '../components/ConvenioEditor'
import { FirmaCanvas } from '../components/FirmaCanvas'

interface AccesoRevisionContraparte {
  codigo_convenio: string | null
  objeto: string | null
  contraparte: string | null
  version_numero: number
  contenido: Record<string, unknown>
  estado: string
  expira_en: string
  correo_destino: string
}

interface DecisionRevisionContraparte {
  estado: string
  resultado: string
}

type CodigoEnlace = 'ENLACE_INVALIDO' | 'ENLACE_EXPIRADO' | 'ENLACE_NO_DISPONIBLE'
type Decision = 'APROBAR' | 'DEVOLVER' | null

function tokenDesdeFragmento(): string | null {
  const parametros = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const token = parametros.get('token')?.trim()
  return token || null
}

function codigoEnlace(error: unknown): CodigoEnlace | null {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== 'object' || Array.isArray(error.detail)) {
    return null
  }
  if (!('codigo' in error.detail) || typeof error.detail.codigo !== 'string') return null
  return ['ENLACE_INVALIDO', 'ENLACE_EXPIRADO', 'ENLACE_NO_DISPONIBLE'].includes(error.detail.codigo)
    ? error.detail.codigo as CodigoEnlace
    : null
}

function fechaHora(valor: string): string {
  return new Date(valor).toLocaleString()
}

function DialogoDecision({
  titulo,
  pendiente,
  children,
  onCerrar,
}: {
  titulo: string
  pendiente: boolean
  children: ReactNode
  onCerrar: () => void
}) {
  const dialogo = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialogo.current?.showModal()
  }, [])

  return (
    <dialog
      ref={dialogo}
      className="modal modal-decision-contraparte"
      aria-labelledby="decision-contraparte-titulo"
      onCancel={(event) => {
        if (pendiente) event.preventDefault()
      }}
      onClose={onCerrar}
    >
      <div className="modal-header">
        <h2 id="decision-contraparte-titulo">{titulo}</h2>
        <button
          type="button"
          className="btn-icon"
          aria-label="Cerrar"
          disabled={pendiente}
          onClick={() => dialogo.current?.close()}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  )
}

function EstadoEnlace({ codigo }: { codigo: CodigoEnlace | 'ERROR' }) {
  const contenido = codigo === 'ENLACE_EXPIRADO'
    ? {
        titulo: 'Este enlace de revisión ha expirado.',
        texto: 'Solicita a la Oficina de Relaciones Interinstitucionales un nuevo enlace para continuar.',
      }
    : codigo === 'ENLACE_NO_DISPONIBLE'
      ? {
          titulo: 'Este enlace ya no está disponible.',
          texto: 'La revisión ya fue atendida o el enlace fue reemplazado. Si necesitas ayuda, comunícate con la ORI.',
        }
      : codigo === 'ENLACE_INVALIDO'
        ? {
            titulo: 'El enlace de revisión no es válido.',
            texto: 'Verifica que abriste el enlace completo recibido por correo o solicita asistencia a la ORI.',
          }
        : {
            titulo: 'No se pudo cargar la revisión.',
            texto: 'Intenta nuevamente. Si el problema continúa, comunícate con la ORI.',
          }

  return (
    <main className="revision-publica-main">
      <section className="card estado-vacio revision-publica-estado" role="alert">
        <span className="revision-publica-marca" aria-hidden="true">ORI</span>
        <h1>{contenido.titulo}</h1>
        <p>{contenido.texto}</p>
      </section>
    </main>
  )
}

export function RevisionContrapartePublicaPage() {
  const notify = useNotifications()
  const [token, setToken] = useState<string | null>(() => tokenDesdeFragmento())
  const [decision, setDecision] = useState<Decision>(null)
  const [finalizado, setFinalizado] = useState<'APROBADA' | 'DEVUELTA' | null>(null)
  const [codigoFinal, setCodigoFinal] = useState<CodigoEnlace | null>(null)
  const [nombreAprobacion, setNombreAprobacion] = useState('')
  const [cargoAprobacion, setCargoAprobacion] = useState('')
  const [firma, setFirma] = useState<string | null>(null)
  const [conformidad, setConformidad] = useState(false)
  const [nombreDevolucion, setNombreDevolucion] = useState('')
  const [cargoDevolucion, setCargoDevolucion] = useState('')
  const [observaciones, setObservaciones] = useState([''])

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`)
    }
  }, [])

  const acceso = useQuery({
    queryKey: ['revision-contraparte-publica', 'acceso'],
    queryFn: () => apiFetch<AccesoRevisionContraparte>('/public/revision-contraparte/acceso', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
    enabled: Boolean(token),
    retry: false,
    gcTime: 0,
  })

  function procesarError(error: unknown, mensaje: string) {
    const codigo = codigoEnlace(error)
    if (codigo) {
      setCodigoFinal(codigo)
      setDecision(null)
      return
    }
    notify({ type: 'error', message: error instanceof Error ? error.message : mensaje })
  }

  const aprobar = useMutation({
    mutationFn: (payload: { nombre: string; cargo: string; firma: string }) =>
      apiFetch<DecisionRevisionContraparte>('/public/revision-contraparte/aprobar', {
        method: 'POST',
        body: JSON.stringify({
          token,
          nombre_firmante: payload.nombre,
          cargo_firmante: payload.cargo,
          firma: payload.firma,
        }),
      }),
    onSuccess: () => {
      setDecision(null)
      setFinalizado('APROBADA')
      setToken(null)
    },
    onError: (error) => procesarError(error, 'No fue posible registrar la aprobación.'),
  })

  const devolver = useMutation({
    mutationFn: (payload: { nombre: string; cargo: string; observaciones: string[] }) =>
      apiFetch<DecisionRevisionContraparte>('/public/revision-contraparte/devolver', {
        method: 'POST',
        body: JSON.stringify({
          token,
          nombre_firmante: payload.nombre,
          cargo_firmante: payload.cargo,
          observaciones: payload.observaciones,
        }),
      }),
    onSuccess: () => {
      setDecision(null)
      setFinalizado('DEVUELTA')
      setToken(null)
    },
    onError: (error) => procesarError(error, 'No fue posible enviar las observaciones.'),
  })

  const observacionesNormalizadas = observaciones.map((item) => item.trim())
  const puedeAprobar = nombreAprobacion.trim() && cargoAprobacion.trim() && firma && conformidad
  const puedeDevolver = nombreDevolucion.trim()
    && cargoDevolucion.trim()
    && observacionesNormalizadas.length > 0
    && observacionesNormalizadas.every(Boolean)
  const decisionPendiente = aprobar.isPending || devolver.isPending

  function agregarObservacion() {
    setObservaciones((actuales) => [...actuales, ''])
  }

  function eliminarObservacion(indice: number) {
    setObservaciones((actuales) => actuales.filter((_, actual) => actual !== indice))
  }

  function actualizarObservacion(indice: number, valor: string) {
    setObservaciones((actuales) => actuales.map((item, actual) => actual === indice ? valor : item))
  }

  let contenido: ReactNode
  if (finalizado) {
    contenido = (
      <main className="revision-publica-main">
        <section className="card estado-vacio revision-publica-estado" role="status">
          <span className="revision-publica-exito" aria-hidden="true">✓</span>
          <h1>Revisión enviada correctamente.</h1>
          <p>
            {finalizado === 'APROBADA'
              ? 'La Universidad continuará con las siguientes etapas del proceso.'
              : 'La elaboración de convenio regresará a la ORI para atender las observaciones y continuar su trámite.'}
          </p>
        </section>
      </main>
    )
  } else if (codigoFinal) {
    contenido = <EstadoEnlace codigo={codigoFinal} />
  } else if (!token) {
    contenido = <EstadoEnlace codigo="ENLACE_INVALIDO" />
  } else if (acceso.isPending) {
    contenido = <main className="revision-publica-main"><p className="estado-pagina">Cargando revisión de contraparte…</p></main>
  } else if (acceso.isError) {
    contenido = <EstadoEnlace codigo={codigoEnlace(acceso.error) ?? 'ERROR'} />
  } else if (!acceso.data) {
    contenido = <EstadoEnlace codigo="ERROR" />
  } else {
    const revision = acceso.data
    contenido = (
      <main className="revision-publica-main">
        <section className="revision-publica-presentacion">
          <span className="badge badge-pendiente">Revisión pendiente</span>
          <h1>Revisión de elaboración de convenio</h1>
          <p>Consulta la versión recibida y registra tu decisión como contraparte.</p>
        </section>

        <section className="card revision-publica-resumen" aria-labelledby="datos-convenio-titulo">
          <h2 id="datos-convenio-titulo">Datos de la elaboración de convenio</h2>
          <dl className="proyecto-datos">
            <dt>Código</dt><dd>{revision.codigo_convenio ?? 'En asignación'}</dd>
            <dt>Contraparte</dt><dd>{revision.contraparte ?? '—'}</dd>
            <dt>Versión recibida</dt><dd>{revision.version_numero}</dd>
            <dt>Destinatario</dt><dd>{revision.correo_destino}</dd>
            <dt>Enlace válido hasta</dt><dd>{fechaHora(revision.expira_en)}</dd>
            <dt>Estado</dt><dd>{revision.estado}</dd>
          </dl>
          <h3>Objeto</h3>
          <p>{revision.objeto ?? '—'}</p>
        </section>

        <section className="card revision-publica-documento" aria-labelledby="documento-convenio-titulo">
          <div className="editor-cabecera">
            <div>
              <h2 id="documento-convenio-titulo">Versión {revision.version_numero} de la elaboración de convenio</h2>
              <p className="section-help">Documento recibido para consulta. Su contenido es de solo lectura.</p>
            </div>
            <span className="badge badge-neutral">Solo lectura</span>
          </div>
          <ConvenioEditor contenido={revision.contenido} editable={false} onChange={() => undefined} />
        </section>

        <section className="card revision-publica-acciones" aria-labelledby="decision-titulo">
          <h2 id="decision-titulo">Registrar decisión</h2>
          <p>Confirma la conformidad con la versión recibida o devuélvela a la ORI indicando las observaciones que deben atenderse.</p>
          <div className="page-toolbar">
            <button className="btn btn-primary" type="button" onClick={() => setDecision('APROBAR')} disabled={decisionPendiente}>
              Aprobar elaboración de convenio
            </button>
            <button className="btn btn-outline" type="button" onClick={() => setDecision('DEVOLVER')} disabled={decisionPendiente}>
              Devolver con observaciones
            </button>
          </div>
        </section>

        {decision === 'APROBAR' && (
          <DialogoDecision titulo="Firma de conformidad" pendiente={aprobar.isPending} onCerrar={() => setDecision(null)}>
            <section className="modal-section">
              <p className="section-help">La firma representa la conformidad de la contraparte con la versión {revision.version_numero}.</p>
              <label className="form-group" htmlFor="nombre-aprobacion">
                <span className="form-label">Nombre del firmante *</span>
                <input id="nombre-aprobacion" className="form-control" value={nombreAprobacion} maxLength={160} disabled={aprobar.isPending} onChange={(event) => setNombreAprobacion(event.target.value)} />
              </label>
              <label className="form-group" htmlFor="cargo-aprobacion">
                <span className="form-label">Cargo *</span>
                <input id="cargo-aprobacion" className="form-control" value={cargoAprobacion} maxLength={160} disabled={aprobar.isPending} onChange={(event) => setCargoAprobacion(event.target.value)} />
              </label>
              <label className="form-group" htmlFor="correo-aprobacion">
                <span className="form-label">Correo destinatario</span>
                <input id="correo-aprobacion" className="form-control" value={revision.correo_destino} readOnly />
              </label>
              <FirmaCanvas disabled={aprobar.isPending} onFirma={setFirma} />
              <label className="conformidad-check">
                <input type="checkbox" checked={conformidad} disabled={aprobar.isPending} onChange={(event) => setConformidad(event.target.checked)} />
                <span>Confirmo que revisé y apruebo la versión {revision.version_numero} de la elaboración de convenio.</span>
              </label>
            </section>
            <div className="modal-acciones">
              <button type="button" className="btn btn-outline" disabled={aprobar.isPending} onClick={() => setDecision(null)}>Cancelar</button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!puedeAprobar || aprobar.isPending}
                onClick={() => {
                  if (!firma) return
                  aprobar.mutate({ nombre: nombreAprobacion.trim(), cargo: cargoAprobacion.trim(), firma })
                }}
              >
                {aprobar.isPending ? 'Registrando aprobación…' : 'Firmar y aprobar'}
              </button>
            </div>
          </DialogoDecision>
        )}

        {decision === 'DEVOLVER' && (
          <DialogoDecision titulo="Devolver con observaciones" pendiente={devolver.isPending} onCerrar={() => setDecision(null)}>
            <section className="modal-section">
              <p className="section-help">La elaboración de convenio regresará a la ORI para que se atiendan las observaciones.</p>
              <label className="form-group" htmlFor="nombre-devolucion">
                <span className="form-label">Nombre *</span>
                <input id="nombre-devolucion" className="form-control" value={nombreDevolucion} maxLength={160} disabled={devolver.isPending} onChange={(event) => setNombreDevolucion(event.target.value)} />
              </label>
              <label className="form-group" htmlFor="cargo-devolucion">
                <span className="form-label">Cargo *</span>
                <input id="cargo-devolucion" className="form-control" value={cargoDevolucion} maxLength={160} disabled={devolver.isPending} onChange={(event) => setCargoDevolucion(event.target.value)} />
              </label>
              <div className="devolucion-observaciones">
                {observaciones.map((observacion, indice) => (
                  <div className="observacion-borrador" key={indice}>
                    <label className="form-group" htmlFor={`observacion-${indice}`}>
                      <span className="form-label">Observación {indice + 1} *</span>
                      <textarea id={`observacion-${indice}`} className="form-control" value={observacion} disabled={devolver.isPending} onChange={(event) => actualizarObservacion(indice, event.target.value)} />
                    </label>
                    {observaciones.length > 1 && (
                      <button className="btn btn-outline btn-small" type="button" disabled={devolver.isPending} onClick={() => eliminarObservacion(indice)}>
                        Eliminar observación
                      </button>
                    )}
                  </div>
                ))}
                <button className="btn btn-outline btn-small" type="button" disabled={devolver.isPending} onClick={agregarObservacion}>
                  + Agregar observación
                </button>
              </div>
            </section>
            <div className="modal-acciones">
              <button type="button" className="btn btn-outline" disabled={devolver.isPending} onClick={() => setDecision(null)}>Cancelar</button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={!puedeDevolver || devolver.isPending}
                onClick={() => devolver.mutate({
                  nombre: nombreDevolucion.trim(),
                  cargo: cargoDevolucion.trim(),
                  observaciones: observacionesNormalizadas,
                })}
              >
                {devolver.isPending ? 'Enviando observaciones…' : 'Confirmar devolución'}
              </button>
            </div>
          </DialogoDecision>
        )}
      </main>
    )
  }

  return (
    <div className="revision-publica-shell">
      <header className="revision-publica-header">
        <div>
          <strong>ORI</strong>
          <span>Oficina de Relaciones Interinstitucionales</span>
        </div>
        <span>Revisión externa de elaboración de convenio</span>
      </header>
      {contenido}
      <footer className="revision-publica-footer">Universidad de San Buenaventura · Gestión de convenios</footer>
    </div>
  )
}

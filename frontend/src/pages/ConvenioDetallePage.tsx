import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { type Convenio } from './epica02'

interface SnapshotRevision {
  objeto?: string | null
  alcance?: string | null
  tipo_convenio_id?: number | null
  implicacion_financiera?: string | null
  duracion_meses?: number | null
  fecha_inicio?: string | null
  fecha_vencimiento?: string | null
}

interface Revision {
  id: number
  tipo: string
  estado: string
  resultado: string | null
  snapshot_datos: SnapshotRevision | null
  creado_en: string
  observaciones: { id: number; descripcion: string; estado: string }[]
}

interface DocumentoConvenio {
  id: number
  tipo: string
  nombre_archivo: string
  tipo_mime: string
  tamano_bytes: number
}

interface RevisionPendiente {
  convenio: {
    tipo_convenio: {
      id: number
      nombre: string
    } | null
  }
  revision_pendiente: Revision
  documentos: DocumentoConvenio[]
}

function fecha(valor: string | null | undefined) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ConvenioDetallePage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const cliente = useQueryClient()
  const notify = useNotifications()
  const { puede } = useSesion()
  const [observaciones, setObservaciones] = useState('')
  const [errorObservacion, setErrorObservacion] = useState(false)
  const convenio = useQuery({
    queryKey: ['convenio', id],
    queryFn: () => apiFetch<Convenio>(`/convenios/${id}`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })
  const consultaRevision = useQuery({
    queryKey: ['convenio', id, 'revision'],
    queryFn: () => apiFetch<RevisionPendiente>(`/convenios/${id}/revision`),
    enabled: Number.isInteger(id) && id > 0 && puede('convenios.revisar'),
    retry: false,
  })
  const accion = useMutation({
    mutationFn: ({ revisionId, tipo, textos }: { revisionId: number; tipo: 'aprobar' | 'devolver'; textos?: string[] }) =>
      apiFetch(`/convenios/${id}/revisiones/${revisionId}/${tipo}`, {
        method: 'POST',
        ...(textos ? { body: JSON.stringify({ observaciones: textos }) } : {}),
      }),
    onSuccess: async (_, variables) => {
      setObservaciones('')
      setErrorObservacion(false)
      notify({
        type: 'success',
        message: variables.tipo === 'aprobar'
          ? 'Revisión jurídica aprobada correctamente.'
          : 'Convenio devuelto a Elaboración con observaciones.',
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['convenio', id] }),
        cliente.invalidateQueries({ queryKey: ['convenio', id, 'revision'] }),
        cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'] }),
      ])
    },
    onError: (error) => notify({
      type: 'error',
      message: error instanceof Error ? error.message : 'No se pudo guardar la revisión.',
    }),
  })
  const revision = consultaRevision.data?.revision_pendiente
  const puedeActuar = puede('convenios.revisar') && revision !== undefined

  function devolver(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = observaciones.trim()
    if (!texto) {
      setErrorObservacion(true)
      return
    }
    if (!revision || accion.isPending) return
    setErrorObservacion(false)
    accion.mutate({ revisionId: revision.id, tipo: 'devolver', textos: [texto] })
  }

  if (convenio.isPending) return <p className="estado-pagina">Cargando convenio…</p>
  if (convenio.isError) return <section className="card estado-vacio"><h1>{convenio.error instanceof ApiError && convenio.error.status === 404 ? 'Convenio no encontrado' : 'No se pudo consultar el convenio'}</h1></section>
  if (!convenio.data) return null
  const datos = convenio.data
  const snapshot = revision?.snapshot_datos

  return (
    <>
      <section className="header-banner"><h1>Convenio {datos.codigo ?? `#${datos.id}`}</h1><p><span className="badge">{datos.estado}</span></p></section>
      <div className="page-toolbar">
        {puede('convenios.editar') && <Link className="btn btn-primary" to={`/convenios/${datos.id}/elaboracion`}>Ir a Elaboración</Link>}
        <Link className="btn btn-outline" to={`/convenios/${datos.id}/historial`}>Ver historial y trazabilidad</Link>
      </div>
      <section className="card"><h2>Información base</h2><dl><dt>Solicitud</dt><dd>#{datos.solicitud_id}</dd><dt>Objeto</dt><dd>{datos.objeto ?? '—'}</dd><dt>Alcance</dt><dd>{datos.alcance ?? '—'}</dd><dt>Aliado</dt><dd>{datos.aliado ? <Link to={`/aliados/${datos.aliado.id}`}>{datos.aliado.nombre}</Link> : 'Sin aliado asociado'}</dd><dt>Responsable</dt><dd>{datos.creado_por.nombre_completo} ({datos.creado_por.correo})</dd><dt>Fecha de creación</dt><dd>{fecha(datos.creado_en)}</dd></dl></section>
      {puede('convenios.revisar') && <section className="card">
        <h2>Revisión jurídica</h2>
        {consultaRevision.isPending && <p>Cargando revisión…</p>}
        {consultaRevision.isError && <p>No hay una revisión jurídica disponible para este convenio.</p>}
        {revision && <>
          <p className="version-revision"><strong>Ronda jurídica #{revision.id}</strong> · Entregada a revisión: {fecha(revision.creado_en)}</p>
          <dl className="summary-grid snapshot-revision">
            <p><dt>Objeto</dt><dd>{snapshot?.objeto ?? '—'}</dd></p>
            <p><dt>Alcance</dt><dd>{snapshot?.alcance ?? '—'}</dd></p>
            <p><dt>Tipo de convenio</dt><dd>
              {consultaRevision.data?.convenio.tipo_convenio?.nombre ?? '—'}
            </dd></p>
            <p><dt>Implicación financiera</dt><dd>{snapshot?.implicacion_financiera ?? '—'}</dd></p>
            <p><dt>Duración</dt><dd>{snapshot?.duracion_meses != null ? `${snapshot.duracion_meses} meses` : '—'}</dd></p>
            <p><dt>Fechas</dt><dd>{fecha(snapshot?.fecha_inicio)} – {fecha(snapshot?.fecha_vencimiento)}</dd></p>
          </dl>
          <div className="documentos-revision">
            <h3>Documentos asociados</h3>
            {consultaRevision.data?.documentos.length === 0 && <p>Sin documentos vigentes asociados al expediente.</p>}
            {consultaRevision.data?.documentos.map((doc) => (
              <div className="document-row" key={doc.id}>
                <span><strong>{doc.tipo}</strong><br />{doc.nombre_archivo} · {tamanoLegible(doc.tamano_bytes)}</span>
                <a className="btn btn-outline btn-small" href={`/api/convenios/${id}/documentos/${doc.id}/contenido`} target="_blank" rel="noreferrer">Ver documento</a>
              </div>
            ))}
          </div>
        </>}
        {puedeActuar && <div className="revision-acciones">
          <button className="btn btn-primary" type="button" disabled={accion.isPending} onClick={() => accion.mutate({ revisionId: revision.id, tipo: 'aprobar' })}>Aprobar convenio</button>
          <form onSubmit={devolver}>
            <div className="form-group">
              <label className="form-label" htmlFor="observaciones-devolucion">Observaciones para devolver</label>
              <textarea
                id="observaciones-devolucion"
                className={`form-control ${errorObservacion ? 'is-invalid' : ''}`}
                value={observaciones}
                onChange={(evento) => { setObservaciones(evento.target.value); setErrorObservacion(false) }}
                placeholder="Describa las correcciones requeridas antes de aprobar el convenio."
                required
                aria-invalid={errorObservacion}
                aria-describedby={errorObservacion ? 'observaciones-devolucion-error' : undefined}
              />
              {errorObservacion && <span id="observaciones-devolucion-error" className="form-error">La observación es obligatoria.</span>}
            </div>
            <button className="btn btn-outline" type="submit" disabled={accion.isPending}>Devolver convenio</button>
          </form>
        </div>}
      </section>}
    </>
  )
}

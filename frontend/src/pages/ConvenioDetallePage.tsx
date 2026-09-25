import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useSesion } from '../auth/sesion'
import { type Convenio } from './epica02'

interface Revision {
  id: number
  tipo: string
  estado: string
  resultado: string | null
  snapshot_datos: { objeto?: string | null } | null
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
  revision_pendiente: Revision
  documentos: DocumentoConvenio[]
}

function fecha(valor: string | null) {
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
  const { puede } = useSesion()
  const [observaciones, setObservaciones] = useState('')
  const [errorAccion, setErrorAccion] = useState<string | null>(null)
  const convenio = useQuery({
    queryKey: ['convenio', id],
    queryFn: () => apiFetch<Convenio>(`/convenios/${id}`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })
  const historial = useQuery({
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
    onSuccess: async () => {
      setErrorAccion(null)
      setObservaciones('')
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['convenio', id] }),
        cliente.invalidateQueries({ queryKey: ['convenio', id, 'revision'] }),
      ])
    },
    onError: (error) => setErrorAccion(error instanceof Error ? error.message : 'No se pudo guardar la revisión'),
  })
  const revision = historial.data?.revision_pendiente
  const puedeActuar = puede('convenios.revisar') && revision !== undefined

  function devolver(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = observaciones.trim()
    if (!revision || !texto || accion.isPending) return
    accion.mutate({ revisionId: revision.id, tipo: 'devolver', textos: [texto] })
  }

  if (convenio.isPending) return <p className="estado-pagina">Cargando convenio…</p>
  if (convenio.isError) return <section className="card estado-vacio"><h1>{convenio.error instanceof ApiError && convenio.error.status === 404 ? 'Convenio no encontrado' : 'No se pudo consultar el convenio'}</h1></section>
  if (!convenio.data) return null
  const datos = convenio.data
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
        {historial.isPending && <p>Cargando revisión…</p>}
        {historial.isError && <p>No hay una revisión jurídica disponible para este convenio.</p>}
        {!historial.isPending && !historial.isError && !revision && <p>No hay una revisión jurídica pendiente.</p>}
        {revision && <p className="version-revision">Versión objeto de revisión: <strong>{revision.snapshot_datos?.objeto ?? datos.objeto ?? '—'}</strong> (entregada a Jurídica el {fecha(revision.creado_en)})</p>}
        {revision && <div className="documentos-revision">
          <h3>Documentos asociados</h3>
          {historial.data?.documentos.length === 0 && <p>Sin documentos cargados para este convenio.</p>}
          {historial.data?.documentos.map((doc) => (
            <div className="document-row" key={doc.id}><span>{doc.tipo}: {doc.nombre_archivo} · {tamanoLegible(doc.tamano_bytes)}</span></div>
          ))}
        </div>}
        {puedeActuar && <>
          <button className="btn btn-primary" type="button" disabled={accion.isPending} onClick={() => accion.mutate({ revisionId: revision.id, tipo: 'aprobar' })}>Aprobar convenio</button>
          <form onSubmit={devolver}>
            <label htmlFor="observaciones-devolucion">Observaciones para devolver</label>
            <textarea id="observaciones-devolucion" value={observaciones} onChange={(evento) => setObservaciones(evento.target.value)} required />
            <button className="btn btn-secondary" type="submit" disabled={!observaciones.trim() || accion.isPending}>Devolver convenio</button>
          </form>
          {errorAccion && <p role="alert">{errorAccion}</p>}
        </>}
      </section>}
    </>
  )
}

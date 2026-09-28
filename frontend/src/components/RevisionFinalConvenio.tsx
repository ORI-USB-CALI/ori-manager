import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import type {
  ElaboracionConvenio,
  ObservacionRevision,
  RevisionConvenioTrazabilidad,
  VersionConvenioResumen,
} from '../pages/epica02'
import { ConfirmacionModal } from './ConfirmacionModal'
import { ConvenioEditor, type DocumentoConvenio } from './ConvenioEditor'

interface DocumentoAsociado {
  id: number
  tipo: string
  nombre_archivo: string
  tipo_mime: string
  tamano_bytes: number
  creado_en: string
}

interface VersionAprobadaContraparte extends VersionConvenioResumen {
  contenido: DocumentoConvenio
  snapshot_metadata: Record<string, unknown>
}

interface RevisionFinal {
  convenio: ElaboracionConvenio
  documentos: DocumentoAsociado[]
  revision_pendiente: RevisionConvenioTrazabilidad
  version_aprobada_contraparte: VersionAprobadaContraparte
  revisiones_juridicas: RevisionConvenioTrazabilidad[]
  revision_contraparte: RevisionConvenioTrazabilidad
  observaciones_pendientes: ObservacionRevision[]
  revision_final_aprobada: boolean
  proceso_firmas_abierto: boolean
}

function fecha(valor: string | null | undefined): string {
  return valor ? new Date(valor).toLocaleString() : '—'
}

function etiqueta(valor: string | null | undefined): string {
  if (!valor) return '—'
  return valor.toLowerCase().replaceAll('_', ' ').replace(/^./, (letra) => letra.toUpperCase())
}

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function mensajeError(error: unknown, respaldo: string): string {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return respaldo
}

export function RevisionFinalConvenio({ convenioId }: { convenioId: number }) {
  const cliente = useQueryClient()
  const notify = useNotifications()
  const [mostrarDevolucion, setMostrarDevolucion] = useState(false)
  const [observacion, setObservacion] = useState('')

  const revisionFinal = useQuery({
    queryKey: ['convenio', convenioId, 'revision-final'],
    queryFn: () => apiFetch<RevisionFinal>(`/convenios/${convenioId}/revision-final`),
    retry: false,
  })

  async function refrescarConvenio() {
    await Promise.all([
      cliente.invalidateQueries({ queryKey: ['convenio', convenioId] }),
      cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'revision-final'] }),
      cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'firmas'] }),
      cliente.invalidateQueries({ queryKey: ['convenio', convenioId, 'historial'] }),
      cliente.invalidateQueries({ queryKey: ['convenios', convenioId, 'elaboracion'] }),
    ])
  }

  const aprobar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/revision-final/aprobar`, {
      method: 'POST',
      body: JSON.stringify({
        expected_version: revisionFinal.data?.version_aprobada_contraparte.numero,
      }),
    }),
    onSuccess: async () => {
      notify({
        type: 'success',
        message: 'La revisión final fue aprobada. El convenio está listo para configurar las firmas.',
      })
      await refrescarConvenio()
    },
    onError: (error) => notify({
      type: 'error',
      message: mensajeError(error, 'No fue posible aprobar la revisión final.'),
    }),
  })

  const devolver = useMutation({
    mutationFn: () => apiFetch(`/convenios/${convenioId}/revision-final/devolver`, {
      method: 'POST',
      body: JSON.stringify({
        expected_version: revisionFinal.data?.version_aprobada_contraparte.numero,
        observaciones: [observacion.trim()],
      }),
    }),
    onSuccess: async () => {
      setMostrarDevolucion(false)
      setObservacion('')
      notify({
        type: 'success',
        message: 'La elaboración de convenio fue devuelta con observaciones.',
      })
      await refrescarConvenio()
    },
    onError: (error) => notify({
      type: 'error',
      message: mensajeError(error, 'No fue posible devolver la elaboración de convenio.'),
    }),
  })

  if (revisionFinal.isPending) {
    return <p className="estado-pagina">Cargando revisión final ORI…</p>
  }
  if (revisionFinal.isError || !revisionFinal.data) {
    return (
      <p className="alert-error" role="alert">
        {mensajeError(revisionFinal.error, 'No fue posible consultar la revisión final ORI.')}
      </p>
    )
  }

  const datos = revisionFinal.data
  const version = datos.version_aprobada_contraparte
  const contraparte = datos.revision_contraparte
  const respuestaContraparte = contraparte.respuesta_contraparte
  const procesando = aprobar.isPending || devolver.isPending
  const puedeAprobar = datos.observaciones_pendientes.length === 0

  return (
    <>
      <section className="revision-workspace" aria-labelledby="revision-final-titulo">
        <main className="card revision-documento">
          <div className="editor-cabecera">
            <div>
              <h2 id="revision-final-titulo">Revisión final ORI</h2>
              <p className="section-help">
                Versión {version.numero}, aprobada por la contraparte. El documento es de solo lectura.
              </p>
            </div>
            <span className="badge badge-neutral">Solo lectura</span>
          </div>
          <ConvenioEditor contenido={version.contenido} editable={false} onChange={() => undefined} />
        </main>

        <aside className="revision-panel">
          <section className="card proyecto-resumen">
            <h2>Condiciones de revisión</h2>
            <dl className="proyecto-datos">
              <dt>Versión aprobada</dt><dd>{version.numero}</dd>
              <dt>Resultado de contraparte</dt><dd>{etiqueta(contraparte.resultado)}</dd>
              <dt>Aprobada por</dt><dd>{respuestaContraparte?.nombre_firmante ?? contraparte.resuelta_por?.nombre_completo ?? '—'}</dd>
              <dt>Cargo</dt><dd>{respuestaContraparte?.cargo_firmante ?? '—'}</dd>
              <dt>Fecha de respuesta</dt><dd>{fecha(respuestaContraparte?.creado_en ?? contraparte.resuelta_en)}</dd>
              <dt>Revisiones jurídicas</dt><dd>{datos.revisiones_juridicas.length}</dd>
              <dt>Observaciones pendientes</dt><dd>{datos.observaciones_pendientes.length}</dd>
              <dt>Estado de revisión final</dt><dd>{etiqueta(datos.revision_pendiente.estado)}</dd>
            </dl>
          </section>

          <section className="card">
            <h2>Documentos asociados</h2>
            {datos.documentos.length === 0 && <p className="section-help">No hay documentos vigentes asociados.</p>}
            {datos.documentos.map((documento) => (
              <div className="document-row" key={documento.id}>
                <span><strong>{documento.tipo}</strong><br />{documento.nombre_archivo} · {tamanoLegible(documento.tamano_bytes)}</span>
                <a className="btn btn-outline btn-small" href={`/api/convenios/${convenioId}/documentos/${documento.id}/contenido`} target="_blank" rel="noreferrer">Ver</a>
              </div>
            ))}
          </section>

          <section className="card revision-decision">
            <h2>Decisión</h2>
            <button className="btn btn-primary btn-block" type="button" disabled={!puedeAprobar || procesando} onClick={() => aprobar.mutate()}>
              {aprobar.isPending ? 'Aprobando…' : 'Aprobar para firmas'}
            </button>
            <button className="btn btn-outline btn-block" type="button" disabled={procesando} onClick={() => setMostrarDevolucion(true)}>
              Devolver con observaciones
            </button>
            {!puedeAprobar && <small>Las observaciones pendientes deben resolverse antes de aprobar para firmas.</small>}
          </section>
        </aside>
      </section>

      {mostrarDevolucion && (
        <ConfirmacionModal
          titulo="Devolver con observaciones"
          confirmar="Devolver con observaciones"
          procesando="Devolviendo…"
          pendiente={devolver.isPending}
          confirmarDeshabilitado={!observacion.trim()}
          onConfirmar={() => devolver.mutate()}
          onCerrar={() => {
            setMostrarDevolucion(false)
            setObservacion('')
          }}
        >
          <p>La elaboración de convenio volverá a la etapa de Elaboración.</p>
          <label className="form-group" htmlFor="observacion-revision-final">
            <span className="form-label">Observación *</span>
            <textarea
              id="observacion-revision-final"
              className="form-control"
              value={observacion}
              onChange={(event) => setObservacion(event.target.value)}
              required
              autoFocus
            />
          </label>
        </ConfirmacionModal>
      )}
    </>
  )
}

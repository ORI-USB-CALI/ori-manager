import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { ConfirmacionModal } from '../components/ConfirmacionModal'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'
import type { RevisionConvenioTrazabilidad, UsuarioResumen, VersionConvenioResumen } from './epica02'
import { CLAVE_REVISIONES_CONTRAPARTE } from './revisionContraparte'

interface DetalleRevisionContraparte {
  convenio_id: number
  codigo_convenio: string | null
  objeto: string | null
  revision: RevisionConvenioTrazabilidad
  version_recibida: VersionConvenioResumen & {
    contenido: DocumentoConvenio
    snapshot_metadata: Record<string, unknown>
  }
  enviada_por: UsuarioResumen
  fecha_envio: string
}

type Decision = 'aprobar' | 'devolver'

function fecha(valor: string) {
  return new Date(valor).toLocaleString()
}

export function RevisionContrapartePage() {
  const revisionId = Number(useParams().revisionId)
  const cliente = useQueryClient()
  const navegar = useNavigate()
  const notify = useNotifications()
  const [decision, setDecision] = useState<Decision | null>(null)
  const [observaciones, setObservaciones] = useState('')
  const detalle = useQuery({
    queryKey: ['revision-contraparte', revisionId],
    queryFn: () => apiFetch<DetalleRevisionContraparte>(`/convenios/revisiones-contraparte/${revisionId}`),
    enabled: Number.isInteger(revisionId) && revisionId > 0,
    retry: false,
  })
  const resolver = useMutation({
    mutationFn: (tipo: Decision) => apiFetch(`/convenios/revisiones-contraparte/${revisionId}/${tipo}`, {
      method: 'POST',
      body: JSON.stringify({
        expected_version: detalle.data?.version_recibida.numero,
        ...(tipo === 'devolver' ? { observaciones: [observaciones.trim()] } : {}),
      }),
    }),
    onSuccess: async (_, tipo) => {
      notify({
        type: 'success',
        message: tipo === 'aprobar'
          ? 'El convenio fue aprobado y pasó a revisión final.'
          : 'El convenio fue devuelto a Elaboración con tus observaciones.',
      })
      await cliente.invalidateQueries({ queryKey: CLAVE_REVISIONES_CONTRAPARTE })
      navegar('/revisiones-contraparte')
    },
    onError: (error) => notify({
      type: 'error',
      message: error instanceof Error ? error.message : 'No fue posible registrar la decisión.',
    }),
  })

  if (detalle.isPending) return <p className="estado-pagina">Cargando revisión…</p>
  if (detalle.isError) {
    const noEncontrada = detalle.error instanceof ApiError && detalle.error.status === 404
    return (
      <section className="card estado-vacio">
        <h1>{noEncontrada ? 'Revisión no encontrada' : 'No se pudo consultar la revisión'}</h1>
        <Link className="btn btn-outline" to="/revisiones-contraparte">Volver a la bandeja</Link>
      </section>
    )
  }
  if (!detalle.data) return null
  const datos = detalle.data
  const pendiente = datos.revision.estado === 'PENDIENTE'

  return (
    <>
      <section className="header-banner">
        <h1>Revisión de contraparte</h1>
        <p>{datos.codigo_convenio ?? `Convenio #${datos.convenio_id}`} · versión {datos.version_recibida.numero}</p>
      </section>
      <div className="revision-workspace">
        <main className="card revision-documento">
          <div className="editor-cabecera">
            <div><h2>Elaboración enviada</h2><p className="section-help">Esta es la versión exacta remitida para tu decisión.</p></div>
            <span className="badge badge-pendiente">{datos.revision.estado}</span>
          </div>
          <ConvenioEditor contenido={datos.version_recibida.contenido} editable={false} onChange={() => undefined} />
        </main>
        <aside className="revision-panel">
          <section className="card proyecto-resumen">
            <h2>Información del envío</h2>
            <dl className="proyecto-datos">
              <dt>Objeto</dt><dd>{datos.objeto ?? '—'}</dd>
              <dt>Versión</dt><dd>{datos.version_recibida.numero}</dd>
              <dt>Enviado por</dt><dd>{datos.enviada_por.nombre_completo}</dd>
              <dt>Correo</dt><dd>{datos.enviada_por.correo}</dd>
              <dt>Fecha</dt><dd>{fecha(datos.fecha_envio)}</dd>
            </dl>
          </section>
          <section className="card revision-decision">
            <h2>Tu decisión</h2>
            <p className="section-help">Aprueba esta versión o devuélvela a la ORI indicando los ajustes requeridos.</p>
            <button className="btn btn-primary btn-block" type="button" disabled={!pendiente} onClick={() => setDecision('aprobar')}>Aprobar elaboración</button>
            <button className="btn btn-outline btn-block" type="button" disabled={!pendiente} onClick={() => setDecision('devolver')}>Devolver con observaciones</button>
          </section>
        </aside>
      </div>
      <div className="page-toolbar"><Link className="btn btn-outline" to="/revisiones-contraparte">Volver a la bandeja</Link></div>

      {decision === 'aprobar' && (
        <ConfirmacionModal titulo="Aprobar elaboración" confirmar="Confirmar aprobación" procesando="Aprobando…" pendiente={resolver.isPending} onConfirmar={() => resolver.mutate('aprobar')} onCerrar={() => setDecision(null)}>
          <p>Confirmas la aprobación de la versión {datos.version_recibida.numero}. El convenio avanzará a revisión final.</p>
        </ConfirmacionModal>
      )}
      {decision === 'devolver' && (
        <ConfirmacionModal titulo="Devolver elaboración" confirmar="Confirmar devolución" procesando="Devolviendo…" pendiente={resolver.isPending} confirmarDeshabilitado={!observaciones.trim()} onConfirmar={() => resolver.mutate('devolver')} onCerrar={() => setDecision(null)}>
          <label className="form-group" htmlFor="observaciones-contraparte">
            <span className="form-label">Observaciones obligatorias</span>
            <textarea id="observaciones-contraparte" className="form-control" value={observaciones} onChange={(event) => setObservaciones(event.target.value)} rows={5} />
          </label>
        </ConfirmacionModal>
      )}
    </>
  )
}

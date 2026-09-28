import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { ConfirmacionModal } from '../components/ConfirmacionModal'
import { ConvenioEditor, type DocumentoConvenio } from '../components/ConvenioEditor'
import { RevisionFinalConvenio } from '../components/RevisionFinalConvenio'
import { SeguimientoFirmasConvenio } from '../components/SeguimientoFirmasConvenio'
import {
  type Convenio,
  type ElaboracionConvenio,
  type HistorialConvenio,
  type InvitacionContraparteTrazabilidad,
} from './epica02'

interface UsuarioResumen { id: number; nombre_completo: string }
interface ObservacionRevision {
  id: number
  descripcion: string
  estado: 'PENDIENTE' | 'ATENDIDA'
  registrada_por: UsuarioResumen
  creado_en: string
}
interface Revision {
  id: number
  tipo: string
  instancia_juridica: 1 | 2 | null
  numero_ronda: number | null
  estado: string
  resultado: string | null
  creado_en: string
  observaciones: ObservacionRevision[]
}
interface DocumentoAsociado { id: number; tipo: string; nombre_archivo: string; tipo_mime: string; tamano_bytes: number }
interface VersionReferencia { id: number; numero: number }
interface RevisionPendiente {
  convenio: Convenio & { tipo_convenio: { id: number; nombre: string } | null }
  revision_pendiente: Revision
  documentos: DocumentoAsociado[]
  version_recibida: VersionReferencia
  version_actual: VersionReferencia & { contenido: DocumentoConvenio }
  version_resultado: VersionReferencia | null
}

function fecha(valor: string | null | undefined) {
  return valor ? new Date(valor).toLocaleString() : '—'
}

function invitacionMasReciente(invitaciones: InvitacionContraparteTrazabilidad[]) {
  return invitaciones.reduce<InvitacionContraparteTrazabilidad | null>((reciente, item) => {
    if (!reciente) return item
    const diferencia = new Date(item.creado_en).getTime() - new Date(reciente.creado_en).getTime()
    return diferencia > 0 || (diferencia === 0 && item.id > reciente.id) ? item : reciente
  }, null)
}

function estadoInvitacion(invitacion: InvitacionContraparteTrazabilidad | null) {
  if (!invitacion || !invitacion.enviado_en) return 'Entrega fallida'
  if (invitacion.revocado_en) return 'Revocada'
  if (invitacion.utilizado_en) return 'Utilizada'
  if (new Date(invitacion.expira_en).getTime() <= Date.now()) return 'Expirada'
  return 'Pendiente'
}

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function esConflictoVersion(error: unknown): error is ApiError {
  if (!(error instanceof ApiError) || error.status !== 409 || !error.detail
    || typeof error.detail !== 'object' || Array.isArray(error.detail)) return false
  return 'expected_version' in error.detail && 'current_version' in error.detail
}

export function ConvenioDetallePage() {
  const id = Number(useParams().convenioId)
  const cliente = useQueryClient()
  const notify = useNotifications()
  const { puede } = useSesion()
  const puedeConsultarEtapa = puede('convenios.editar')
    || puede('convenios.revisar')
    || puede('convenios.gestionar_revision_contraparte')
    || puede('convenios.gestionar_firmas')
  const [borrador, setBorrador] = useState<{ version: number; contenido: DocumentoConvenio } | null>(null)
  const [observacion, setObservacion] = useState('')
  const [confirmarEnvio, setConfirmarEnvio] = useState(false)
  const [confirmarReenvio, setConfirmarReenvio] = useState(false)

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
  const flujoContraparte = useQuery({
    queryKey: ['convenios', id, 'elaboracion'],
    queryFn: () => apiFetch<ElaboracionConvenio>(`/convenios/${id}/elaboracion`),
    enabled: Number.isInteger(id) && id > 0 && puedeConsultarEtapa,
    retry: false,
  })
  const historialContraparte = useQuery({
    queryKey: ['convenio', id, 'historial'],
    queryFn: () => apiFetch<HistorialConvenio>(`/convenios/${id}/revisiones`),
    enabled: Number.isInteger(id) && id > 0 && puede('convenios.gestionar_revision_contraparte'),
    retry: false,
  })
  const versionActual = consultaRevision.data?.version_actual.numero
  const contenido = borrador && borrador.version === versionActual
    ? borrador.contenido
    : consultaRevision.data?.version_actual.contenido
  const revision = consultaRevision.data?.revision_pendiente
  const observacionesPendientes = revision?.observaciones.filter((item) => item.estado === 'PENDIENTE') ?? []
  const observacionSinRegistrar = observacion.trim().length > 0
  const revisionContrapartePendiente = historialContraparte.data?.revisiones.find(
    (item) => item.tipo === 'CONTRAPARTE' && item.estado === 'PENDIENTE',
  )
  const ultimaInvitacion = revisionContrapartePendiente
    ? invitacionMasReciente(revisionContrapartePendiente.invitaciones_contraparte)
    : null

  async function refrescarRevision(limpiarBorrador = true) {
    if (limpiarBorrador) setBorrador(null)
    await Promise.all([
      cliente.invalidateQueries({ queryKey: ['convenio', id] }),
      cliente.invalidateQueries({ queryKey: ['convenio', id, 'revision'] }),
      cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'] }),
      cliente.invalidateQueries({ queryKey: ['revisiones-juridicas', 'pendientes'] }),
    ])
  }

  const guardar = useMutation({
    mutationFn: () => apiFetch(`/convenios/${id}/revisiones/${revision?.id}/contenido`, {
      method: 'PATCH', body: JSON.stringify({ contenido, expected_version: versionActual }),
    }),
    onSuccess: async () => {
      notify({ type: 'success', message: 'Cambios guardados en una nueva versión.' })
      await refrescarRevision()
    },
    onError: (error) => notify({
      type: 'error',
      message: esConflictoVersion(error)
        ? 'El proyecto fue actualizado desde que abriste esta revisión. Recarga la página antes de continuar.'
        : error instanceof Error ? error.message : 'No fue posible guardar el documento.',
    }),
  })
  const agregarObservacion = useMutation({
    mutationFn: () => apiFetch(`/convenios/${id}/revisiones/${revision?.id}/observaciones`, {
      method: 'POST', body: JSON.stringify({ descripcion: observacion.trim() }),
    }),
    onSuccess: async () => {
      setObservacion('')
      notify({ type: 'success', message: 'Observación registrada.' })
      await refrescarRevision(false)
    },
    onError: (error) => notify({ type: 'error', message: error instanceof Error ? error.message : 'No fue posible registrar la observación.' }),
  })
  const resolver = useMutation({
    mutationFn: (tipo: 'aprobar' | 'devolver') => apiFetch(`/convenios/${id}/revisiones/${revision?.id}/${tipo}`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: versionActual, ...(tipo === 'devolver' ? { observaciones: [] } : {}) }),
    }),
    onSuccess: async (_, tipo) => {
      notify({
        type: 'success',
        message: tipo === 'aprobar'
          ? revision?.instancia_juridica === 1
            ? 'Primera revisión aprobada. Se habilitó la segunda revisión.'
            : 'Segunda revisión aprobada. El proyecto quedó habilitado para contraparte.'
          : 'Proyecto devuelto a Elaboración con observaciones.',
      })
      await refrescarRevision()
    },
    onError: (error) => notify({
      type: 'error',
      message: esConflictoVersion(error)
        ? 'El proyecto fue actualizado desde que abriste esta revisión. Recarga la página antes de continuar.'
        : error instanceof Error ? error.message : 'No fue posible resolver la revisión.',
    }),
  })
  const enviarContraparte = useMutation({
    mutationFn: () => apiFetch(`/convenios/${id}/revision-contraparte/enviar`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: convenio.data?.version_actual }),
    }),
    onSuccess: async () => {
      setConfirmarEnvio(false)
      notify({ type: 'success', message: 'La versión aprobada jurídicamente fue enviada a la contraparte.' })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['convenio', id] }),
        cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'] }),
        cliente.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'] }),
      ])
    },
    onError: async (error) => {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'No fue posible enviar la elaboración de convenio a la contraparte.',
      })
      if (error instanceof ApiError && (error.status === 409 || error.status === 502)) {
        setConfirmarEnvio(false)
        await Promise.all([
          cliente.invalidateQueries({ queryKey: ['convenio', id], exact: true }),
          cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'], exact: true }),
          cliente.invalidateQueries({ queryKey: ['convenios', id, 'elaboracion'], exact: true }),
        ])
      }
    },
  })
  const reenviarContraparte = useMutation({
    mutationFn: () => apiFetch(
      `/convenios/${id}/revisiones/${revisionContrapartePendiente?.id}/contraparte/reenviar`,
      { method: 'POST' },
    ),
    onSuccess: async () => {
      setConfirmarReenvio(false)
      notify({ type: 'success', message: 'Se generó y envió un nuevo enlace a la contraparte.' })
      await cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'], exact: true })
    },
    onError: async (error) => {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'No fue posible reenviar el enlace.',
      })
      if (error instanceof ApiError && (error.status === 409 || error.status === 502)) {
        setConfirmarReenvio(false)
        await cliente.invalidateQueries({ queryKey: ['convenio', id, 'historial'], exact: true })
      }
    },
  })

  if (convenio.isPending) return <p className="estado-pagina">Cargando convenio…</p>
  if (convenio.isError) return <section className="card estado-vacio"><h1>{convenio.error instanceof ApiError && convenio.error.status === 404 ? 'Convenio no encontrado' : 'No se pudo consultar el convenio'}</h1></section>
  if (!convenio.data) return null
  const datos = convenio.data
  const etapaActual = flujoContraparte.data?.etapa_actual?.codigo
  const habilitadoParaContraparte = flujoContraparte.data?.etapa_actual?.codigo === 'REVISION_CONTRAPARTE'
  const solicitanteDestino = flujoContraparte.data?.solicitud.solicitante_nombre
    ?? flujoContraparte.data?.solicitud.solicitante_correo
  const puedeEnviarContraparte = puede('convenios.gestionar_revision_contraparte')
    && convenio.isSuccess
    && !convenio.isFetching
    && flujoContraparte.isSuccess
    && !flujoContraparte.isFetching
    && historialContraparte.isSuccess
    && !historialContraparte.isFetching
    && habilitadoParaContraparte
    && !revisionContrapartePendiente
    && datos.version_actual > 0
  const puedeIrAElaboracion = puede('convenios.editar') && etapaActual === 'ELABORACION'

  return (
    <>
      <section className="header-banner">
        <h1>{datos.estado === 'EN_TRAMITE' ? 'Elaboración de convenio' : 'Convenio'} {datos.codigo ?? `#${datos.id}`}</h1>
        <p><span className="badge">{datos.estado}</span></p>
      </section>

      {puede('convenios.gestionar_revision_contraparte') && (flujoContraparte.isPending || historialContraparte.isPending) && (
        <p className="estado-pagina">Verificando disponibilidad para envío a contraparte…</p>
      )}
      {puede('convenios.gestionar_revision_contraparte') && (flujoContraparte.isError || historialContraparte.isError) && (
        <p className="alert-error" role="alert">
          No fue posible verificar si la elaboración de convenio puede enviarse a contraparte.
        </p>
      )}
      {puedeEnviarContraparte && (
        <section className="card revision-contraparte-gestion">
          <div className="revision-contraparte-cabecera">
            <div>
              <h2>Revisión de contraparte</h2>
              <p className="section-help">La versión {datos.version_actual} cuenta con aval jurídico y se enviará al contacto externo mediante un enlace válido por una hora.</p>
            </div>
            <span className="badge badge-neutral">Lista para envío</span>
          </div>
          <dl className="proyecto-datos revision-contraparte-datos">
            <dt>Versión aprobada</dt><dd>{datos.version_actual}</dd>
            <dt>Contacto</dt><dd>{flujoContraparte.data?.solicitud.contacto_contraparte_nombre ?? '—'}</dd>
            <dt>Enviar a</dt><dd>{flujoContraparte.data?.solicitud.contacto_contraparte_correo ?? '—'}</dd>
            <dt>CC informativa</dt><dd>{flujoContraparte.data?.solicitud.solicitante_correo ?? '—'}</dd>
          </dl>
          <div className="page-toolbar">
            <button className="btn btn-primary" type="button" onClick={() => setConfirmarEnvio(true)} disabled={enviarContraparte.isPending || reenviarContraparte.isPending}>
              Enviar a contraparte
            </button>
          </div>
        </section>
      )}
      {puede('convenios.gestionar_revision_contraparte') && habilitadoParaContraparte && revisionContrapartePendiente && (
        <section className="card revision-contraparte-gestion">
          <div className="revision-contraparte-cabecera">
            <div>
              <h2>Revisión de contraparte en curso</h2>
              <p className="section-help">La contraparte externa puede aprobar o devolver la versión recibida mediante su enlace temporal.</p>
            </div>
            <span className={`badge ${ultimaInvitacion?.enviado_en ? 'badge-pendiente' : 'badge-inactivo'}`}>
              {estadoInvitacion(ultimaInvitacion)}
            </span>
          </div>
          {!ultimaInvitacion?.enviado_en && (
            <p className="alert-error" role="alert">La revisión fue creada, pero no fue posible entregar el correo.</p>
          )}
          <dl className="proyecto-datos revision-contraparte-datos">
            <dt>Versión</dt><dd>{revisionContrapartePendiente.version_convenio?.numero ?? '—'}</dd>
            <dt>Enviado a</dt><dd>{ultimaInvitacion?.correo_destino ?? '—'}</dd>
            <dt>CC</dt><dd>{ultimaInvitacion?.correo_cc ?? 'Sin copia'}</dd>
            <dt>Generado por</dt><dd>{ultimaInvitacion?.generada_por.nombre_completo ?? revisionContrapartePendiente.creada_por?.nombre_completo ?? 'ORI'}</dd>
            <dt>Generado</dt><dd>{fecha(ultimaInvitacion?.creado_en ?? revisionContrapartePendiente.creado_en)}</dd>
            <dt>Enviado</dt><dd>{ultimaInvitacion?.enviado_en ? fecha(ultimaInvitacion.enviado_en) : 'Entrega pendiente'}</dd>
            <dt>Expira</dt><dd>{fecha(ultimaInvitacion?.expira_en)}</dd>
          </dl>
          <div className="page-toolbar">
            <button className="btn btn-outline" type="button" onClick={() => setConfirmarReenvio(true)} disabled={reenviarContraparte.isPending || enviarContraparte.isPending}>
              Reenviar enlace
            </button>
          </div>
        </section>
      )}

      {puede('convenios.gestionar_firmas') && etapaActual === 'REVISION_FINAL' && (
        <RevisionFinalConvenio convenioId={id} />
      )}
      {puede('convenios.gestionar_firmas')
        && (etapaActual === 'APROBACION_FIRMAS' || etapaActual === 'FIRMA_ARCHIVO_SEGUIMIENTO') && (
        <SeguimientoFirmasConvenio convenioId={id} />
      )}

      {puede('convenios.revisar') && consultaRevision.isPending && <p className="estado-pagina">Cargando revisión jurídica…</p>}
      {puede('convenios.revisar') && etapaActual === 'REVISION_AVAL_JURIDICO' && consultaRevision.data && revision && contenido ? (
        <div className="revision-workspace">
          <main className="card revision-documento">
            <div className="editor-cabecera">
              <div><h2>Documento jurídico</h2><p className="section-help">Edita directamente el proyecto que estás revisando.</p></div>
              {borrador && <span className="badge badge-pendiente">Cambios sin guardar</span>}
            </div>
            <ConvenioEditor key={versionActual} contenido={contenido} editable onChange={(nuevo) => setBorrador({ version: versionActual!, contenido: nuevo })} />
          </main>

          <aside className="revision-panel">
            <section className="card proyecto-resumen">
              <h2>Revisión jurídica {revision.instancia_juridica} de 2</h2>
              <p className="revision-ronda">Ronda {revision.numero_ronda}</p>
              <dl className="proyecto-datos">
                <dt>Versión recibida</dt><dd>{consultaRevision.data.version_recibida.numero}</dd>
                <dt>Versión actual</dt><dd>{versionActual}</dd>
                <dt>Recibida el</dt><dd>{fecha(revision.creado_en)}</dd>
              </dl>
              <button className="btn btn-outline btn-block" type="button" disabled={!borrador || guardar.isPending} onClick={() => guardar.mutate()}>{guardar.isPending ? 'Guardando…' : 'Guardar cambios'}</button>
            </section>

            <section className="card">
              <h2>Observaciones de la revisión</h2>
              {revision.observaciones.length === 0 && <p className="section-help">Aún no se han registrado observaciones.</p>}
              <div className="revision-observaciones">
                {revision.observaciones.map((item) => <article key={item.id}><p>{item.descripcion}</p><small>{item.registrada_por.nombre_completo} · {fecha(item.creado_en)}</small></article>)}
              </div>
              <label className="form-group" htmlFor="nueva-observacion"><span className="form-label">Nueva observación</span><textarea id="nueva-observacion" className="form-control" value={observacion} onChange={(event) => setObservacion(event.target.value)} /></label>
              <button className="btn btn-outline btn-block" type="button" disabled={Boolean(borrador) || !observacionSinRegistrar || agregarObservacion.isPending} onClick={() => agregarObservacion.mutate()}>+ Agregar observación</button>
              {borrador && <small>Guarda los cambios del documento antes de registrar una observación.</small>}
            </section>

            <section className="card">
              <h2>Documentos asociados</h2>
              {consultaRevision.data.documentos.length === 0 && <p className="section-help">No hay documentos vigentes asociados.</p>}
              {consultaRevision.data.documentos.map((doc) => <div className="document-row" key={doc.id}><span><strong>{doc.tipo}</strong><br />{doc.nombre_archivo} · {tamanoLegible(doc.tamano_bytes)}</span><a className="btn btn-outline btn-small" href={`/api/convenios/${id}/documentos/${doc.id}/contenido`} target="_blank" rel="noreferrer">Ver</a></div>)}
            </section>

            <section className="card revision-decision">
              <h2>Decisión</h2>
              <button className="btn btn-primary btn-block" type="button" disabled={Boolean(borrador) || observacionSinRegistrar || agregarObservacion.isPending || observacionesPendientes.length > 0 || resolver.isPending} onClick={() => resolver.mutate('aprobar')}>Aprobar revisión</button>
              <button className="btn btn-outline btn-block" type="button" disabled={Boolean(borrador) || observacionSinRegistrar || agregarObservacion.isPending || observacionesPendientes.length === 0 || resolver.isPending} onClick={() => resolver.mutate('devolver')}>Devolver a Elaboración</button>
              {borrador && <small>Guarda los cambios antes de registrar la decisión.</small>}
              {observacionSinRegistrar && <small>Registra o elimina la observación escrita antes de tomar una decisión.</small>}
              {observacionesPendientes.length > 0 && <small>Las observaciones pendientes impiden aprobar y permiten devolver el proyecto.</small>}
            </section>
          </aside>
        </div>
      ) : (
        <>
          <div className="page-toolbar">
            {puedeIrAElaboracion && <Link className="btn btn-primary" to={`/convenios/${datos.id}/elaboracion`}>Continuar elaboración</Link>}
          </div>
          <section className="card"><h2>Información base</h2><dl><dt>Solicitud</dt><dd>#{datos.solicitud_id}</dd><dt>Objeto</dt><dd>{datos.objeto ?? '—'}</dd><dt>Alcance</dt><dd>{datos.alcance ?? '—'}</dd><dt>Responsable</dt><dd>{datos.creado_por.nombre_completo}</dd></dl></section>
        </>
      )}
      <div className="page-toolbar"><Link className="btn btn-outline" to={`/convenios/${datos.id}/historial`}>Ver historial y trazabilidad</Link></div>

      {confirmarEnvio && (
        <ConfirmacionModal
          titulo="Enviar elaboración de convenio a contraparte"
          confirmar={`Enviar versión ${datos.version_actual}`}
          procesando="Enviando…"
          pendiente={enviarContraparte.isPending}
          onConfirmar={() => enviarContraparte.mutate()}
          onCerrar={() => setConfirmarEnvio(false)}
        >
          <p>Se enviará la versión {datos.version_actual}, aprobada jurídicamente.</p>
          <p><strong>Destinatario:</strong> {flujoContraparte.data?.solicitud.contacto_contraparte_nombre ?? 'Contacto de contraparte'} · {flujoContraparte.data?.solicitud.contacto_contraparte_correo ?? '—'}</p>
          <p><strong>CC:</strong> {flujoContraparte.data?.solicitud.solicitante_correo ?? solicitanteDestino ?? '—'}</p>
          <p className="texto-secundario">El contacto externo recibirá un enlace temporal para aprobar la versión recibida o devolverla a la ORI con observaciones. El Solicitante recibirá únicamente una copia informativa.</p>
        </ConfirmacionModal>
      )}

      {confirmarReenvio && revisionContrapartePendiente && (
        <ConfirmacionModal
          titulo="Reenviar enlace de revisión"
          confirmar="Generar y reenviar enlace"
          procesando="Reenviando…"
          pendiente={reenviarContraparte.isPending}
          onConfirmar={() => reenviarContraparte.mutate()}
          onCerrar={() => setConfirmarReenvio(false)}
        >
          <p>Se revocará el enlace anterior y se generará uno nuevo para la misma revisión y la misma versión {revisionContrapartePendiente.version_convenio?.numero ?? '—'}.</p>
          <p><strong>Destinatario:</strong> {ultimaInvitacion?.correo_destino ?? '—'}</p>
          <p><strong>CC:</strong> {ultimaInvitacion?.correo_cc ?? 'Sin copia'}</p>
        </ConfirmacionModal>
      )}
    </>
  )
}

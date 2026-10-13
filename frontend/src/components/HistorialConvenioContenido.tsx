import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../app/api'
import type { HistorialConvenio, RevisionConvenioTrazabilidad } from '../pages/epica02'
import { LineaTiempoConvenio } from './LineaTiempoConvenio'
import { ObservacionesJuridicas } from './ObservacionesJuridicas'
import { VersionesSolicitud } from './VersionesSolicitud'

const ETIQUETA_TIPO_REVISION: Record<string, string> = {
  JURIDICA: 'Revisión jurídica',
  CONTRAPARTE: 'Revisión de contraparte',
  FINAL: 'Revisión final',
}

const ETIQUETA_RESULTADO: Record<string, string> = {
  APROBADA: 'Aprobada',
  DEVUELTA: 'Devuelta',
}

const ETIQUETA_ESTADO_OBSERVACION: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  ATENDIDA: 'Atendida',
}

function fechaHora(valor: string | null): string {
  if (!valor) return '—'
  return new Date(valor).toLocaleString()
}

function badgeResultado(revision: RevisionConvenioTrazabilidad): { texto: string; clase: string } {
  if (revision.resultado === 'APROBADA') return { texto: ETIQUETA_RESULTADO.APROBADA, clase: 'badge-activo' }
  if (revision.resultado === 'DEVUELTA') return { texto: ETIQUETA_RESULTADO.DEVUELTA, clase: 'badge-inactivo' }
  return { texto: 'Pendiente', clase: 'badge-pendiente' }
}

interface Props {
  convenioId: number
  /** Solicitud de origen; sin ella no se muestran sus versiones. */
  solicitudId?: number | null
}

function TrazabilidadRevisiones({ convenioId: id, solicitudId }: Props) {
  const historial = useQuery({
    queryKey: ['convenio', id, 'historial'],
    queryFn: () => apiFetch<HistorialConvenio>(`/convenios/${id}/revisiones`),
    enabled: Number.isInteger(id) && id > 0,
    retry: false,
  })

  if (historial.isPending) return <p className="estado-pagina">Cargando historial…</p>
  if (historial.isError) {
    const noEncontrado = historial.error instanceof ApiError && historial.error.status === 404
    return (
      <section className="card estado-vacio">
        <h2>{noEncontrado ? 'Convenio no encontrado' : 'No se pudo consultar el historial'}</h2>
      </section>
    )
  }

  if (!historial.data) return null
  const { revisiones, cambios_etapa: cambiosEtapa } = historial.data

  return (
    <>
      <ObservacionesJuridicas revisiones={revisiones} />

      {solicitudId != null && <VersionesSolicitud solicitudId={solicitudId} />}

      <section className="card">
        <h2>Cambios de etapa</h2>
        {cambiosEtapa.length === 0 && <p>Aún no se han registrado cambios de etapa.</p>}
        {cambiosEtapa.length > 0 && (
          <ol className="timeline">
            {cambiosEtapa.map((cambio) => (
              <li className="timeline-item" key={cambio.id}>
                <p className="timeline-fecha">{fechaHora(cambio.fecha_cambio)}</p>
                <p className="timeline-titulo">
                  {cambio.etapa_origen ? cambio.etapa_origen.nombre : 'Registro del convenio'}
                  {' → '}
                  {cambio.etapa_destino.nombre}
                </p>
                <p className="texto-secundario">
                  Registrado por {cambio.usuario.nombre_completo}
                  {cambio.responsable && cambio.responsable.id !== cambio.usuario.id
                    ? ` · Responsable: ${cambio.responsable.nombre_completo}`
                    : ''}
                </p>
                {cambio.observacion && <p>{cambio.observacion}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="card">
        <h2>Rondas de revisión</h2>
        {revisiones.length === 0 && <p>Aún no se han registrado rondas de revisión.</p>}
        {revisiones.map((revision) => {
          const badge = badgeResultado(revision)
          return (
            <article className="card timeline-revision" key={revision.id}>
              <h3>
                {revision.tipo === 'JURIDICA' && revision.numero_ronda
                  ? `Ronda ${revision.numero_ronda} · Revisión jurídica ${revision.instancia_juridica} de 2`
                  : ETIQUETA_TIPO_REVISION[revision.tipo] ?? revision.tipo}{' '}
                <span className={`badge ${badge.clase}`}>{badge.texto}</span>
              </h3>
              <dl>
                <dt>Objeto revisado</dt>
                <dd>{revision.snapshot_datos?.objeto ?? '—'}</dd>
                <dt>Versión recibida</dt>
                <dd>{revision.version_convenio?.numero ?? 'Legacy'}</dd>
                <dt>Versión resultado</dt>
                <dd>{revision.version_resultado?.numero ?? '—'}</dd>
                <dt>Entregada a revisión</dt>
                <dd>{fechaHora(revision.creado_en)}</dd>
                {revision.creada_por && (
                  <>
                    <dt>{revision.tipo === 'CONTRAPARTE' ? 'Enviada por' : 'Creada por'}</dt>
                    <dd>{revision.creada_por.nombre_completo}</dd>
                  </>
                )}
                {revision.responsable && (
                  <>
                    <dt>Responsable</dt>
                    <dd>{revision.responsable.nombre_completo}</dd>
                  </>
                )}
                {revision.resultado && (
                  <>
                    <dt>Resuelta</dt>
                    <dd>
                      {fechaHora(revision.resuelta_en)}
                      {revision.resuelta_por ? ` · ${revision.resuelta_por.nombre_completo}` : ''}
                    </dd>
                  </>
                )}
              </dl>
              {revision.respuesta_contraparte && (
                <div className="timeline-respuesta-contraparte">
                  <h4>Decisión de la contraparte externa</h4>
                  <dl>
                    <dt>Firmante</dt>
                    <dd>{revision.respuesta_contraparte.nombre_firmante}</dd>
                    <dt>Cargo</dt>
                    <dd>{revision.respuesta_contraparte.cargo_firmante}</dd>
                    <dt>Correo</dt>
                    <dd>{revision.respuesta_contraparte.correo_actor}</dd>
                    <dt>Resultado</dt>
                    <dd>{revision.resultado ? ETIQUETA_RESULTADO[revision.resultado] ?? revision.resultado : '—'}</dd>
                    <dt>Fecha</dt>
                    <dd>{fechaHora(revision.respuesta_contraparte.creado_en)}</dd>
                    <dt>Firma de conformidad</dt>
                    <dd>{revision.respuesta_contraparte.tiene_firma ? 'Registrada' : 'No aplica'}</dd>
                    {revision.respuesta_contraparte.firma_sha256 && (
                      <>
                        <dt>Huella SHA-256</dt>
                        <dd className="texto-hash">{revision.respuesta_contraparte.firma_sha256}</dd>
                      </>
                    )}
                  </dl>
                </div>
              )}
              {revision.invitaciones_contraparte.length > 0 && (
                <div className="timeline-invitaciones">
                  <h4>Invitaciones enviadas</h4>
                  {revision.invitaciones_contraparte.map((invitacion) => (
                    <article className="document-row invitacion-trazabilidad" key={invitacion.id}>
                      <dl>
                        <dt>Generada por</dt><dd>{invitacion.generada_por.nombre_completo}</dd>
                        <dt>Destinatario</dt><dd>{invitacion.correo_destino}</dd>
                        <dt>CC</dt><dd>{invitacion.correo_cc ?? 'Sin copia'}</dd>
                        <dt>Generada</dt><dd>{fechaHora(invitacion.creado_en)}</dd>
                        <dt>Enviada</dt><dd>{fechaHora(invitacion.enviado_en)}</dd>
                        <dt>Expira</dt><dd>{fechaHora(invitacion.expira_en)}</dd>
                        {invitacion.utilizado_en && <><dt>Utilizada</dt><dd>{fechaHora(invitacion.utilizado_en)}</dd></>}
                        {invitacion.revocado_en && <><dt>Revocada</dt><dd>{fechaHora(invitacion.revocado_en)}</dd></>}
                      </dl>
                    </article>
                  ))}
                </div>
              )}
              {revision.observaciones.length > 0 && (
                <div className="timeline-observaciones">
                  <h4>Observaciones</h4>
                  {revision.observaciones.map((observacion) => (
                    <article className="historial-observacion" key={observacion.id} aria-labelledby={`observacion-${observacion.id}-titulo`}>
                      <div className="historial-observacion-cabecera">
                        <strong id={`observacion-${observacion.id}-titulo`}>Observación #{observacion.id}</strong>
                        <span className={`badge ${observacion.estado === 'ATENDIDA' ? 'badge-activo' : 'badge-pendiente'}`}>
                          {ETIQUETA_ESTADO_OBSERVACION[observacion.estado] ?? observacion.estado}
                        </span>
                      </div>
                      <p>{observacion.descripcion}</p>
                      <p className="texto-secundario">
                        {observacion.registrada_por && `Registrada por ${observacion.registrada_por.nombre_completo}`}
                        {observacion.registrada_por && observacion.creado_en && ' · '}
                        {observacion.creado_en && fechaHora(observacion.creado_en)}
                      </p>
                      {observacion.responsable && (
                        <p className="texto-secundario">Responsable: {observacion.responsable.nombre_completo}</p>
                      )}
                      <div className="historial-respuesta" role="group" aria-label={`Respuesta a la observación #${observacion.id}`}>
                        <strong><span aria-hidden="true">↳ </span>Respuesta</strong>
                        {observacion.respuesta ? (
                          <>
                            <p>{observacion.respuesta}</p>
                            {(observacion.atendida_por || observacion.fecha_atencion) && (
                              <p className="texto-secundario">
                                {observacion.atendida_por?.nombre_completo}
                                {observacion.atendida_por && observacion.fecha_atencion && ' · '}
                                {observacion.fecha_atencion && fechaHora(observacion.fecha_atencion)}
                              </p>
                            )}
                          </>
                        ) : <p className="texto-secundario">Pendiente de respuesta</p>}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </article>
          )
        })}
      </section>
    </>
  )
}

/** Trazabilidad del convenio: pestaña Historial del detalle y /convenios/:id/historial. */
export function HistorialConvenioContenido({ convenioId, solicitudId }: Props) {
  return (
    <>
      <LineaTiempoConvenio convenioId={convenioId} />
      <TrazabilidadRevisiones convenioId={convenioId} solicitudId={solicitudId} />
    </>
  )
}

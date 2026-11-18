import { useQuery } from '@tanstack/react-query'

import { CampoLectura, DetalleCampos } from './DetalleCampos'
import { ApiError, apiFetch } from '../app/api'
import type { HistorialConvenio, RevisionConvenioTrazabilidad } from '../pages/epica02'
import { LineaTiempoConvenio } from './LineaTiempoConvenio'
import { ObservacionesJuridicas } from './ObservacionesJuridicas'
import { VersionesConvenio } from './VersionesConvenio'
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

      {solicitudId != null && solicitudId > 0 && <VersionesSolicitud solicitudId={solicitudId} />}

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
              <DetalleCampos>
                <CampoLectura etiqueta="Objeto revisado" amplio>{revision.snapshot_datos?.objeto ?? '—'}</CampoLectura>
                <CampoLectura etiqueta="Versión recibida">{revision.version_convenio?.numero ?? 'Legacy'}</CampoLectura>
                <CampoLectura etiqueta="Versión resultado">{revision.version_resultado?.numero ?? '—'}</CampoLectura>
                <CampoLectura etiqueta="Entregada a revisión">{fechaHora(revision.creado_en)}</CampoLectura>
                {revision.creada_por && (
                  <>
                    <CampoLectura etiqueta={revision.tipo === 'CONTRAPARTE' ? 'Enviada por' : 'Creada por'}>{revision.creada_por.nombre_completo}</CampoLectura>
                  </>
                )}
                {revision.responsable && (
                  <>
                    <CampoLectura etiqueta="Responsable">{revision.responsable.nombre_completo}</CampoLectura>
                  </>
                )}
                {revision.resultado && (
                  <>
                    <CampoLectura etiqueta="Fecha de resolución">{fechaHora(revision.resuelta_en)}</CampoLectura>
                    <CampoLectura etiqueta="Resuelta por">{revision.resuelta_por?.nombre_completo ?? '—'}</CampoLectura>
                  </>
                )}
              </DetalleCampos>
              {revision.respuesta_contraparte && (
                <div className="timeline-respuesta-contraparte">
                  <h4>Decisión de la contraparte externa</h4>
                  <DetalleCampos>
                    <CampoLectura etiqueta="Firmante">{revision.respuesta_contraparte.nombre_firmante}</CampoLectura>
                    <CampoLectura etiqueta="Cargo">{revision.respuesta_contraparte.cargo_firmante}</CampoLectura>
                    <CampoLectura etiqueta="Correo">{revision.respuesta_contraparte.correo_actor}</CampoLectura>
                    <CampoLectura etiqueta="Resultado">{revision.resultado ? ETIQUETA_RESULTADO[revision.resultado] ?? revision.resultado : '—'}</CampoLectura>
                    <CampoLectura etiqueta="Fecha">{fechaHora(revision.respuesta_contraparte.creado_en)}</CampoLectura>
                    <CampoLectura etiqueta="Firma de conformidad">{revision.respuesta_contraparte.tiene_firma ? 'Registrada' : 'No aplica'}</CampoLectura>
                    {revision.respuesta_contraparte.firma_sha256 && (
                      <>
                        <CampoLectura etiqueta="Huella SHA-256" amplio className="texto-hash">{revision.respuesta_contraparte.firma_sha256}</CampoLectura>
                      </>
                    )}
                  </DetalleCampos>
                </div>
              )}
              {revision.invitaciones_contraparte.length > 0 && (
                <div className="timeline-invitaciones">
                  <h4>Invitaciones enviadas</h4>
                  {revision.invitaciones_contraparte.map((invitacion) => (
                    <article className="document-row invitacion-trazabilidad" key={invitacion.id}>
                      <DetalleCampos>
                        <CampoLectura etiqueta="Generada por">{invitacion.generada_por.nombre_completo}</CampoLectura>
                        <CampoLectura etiqueta="Destinatario">{invitacion.correo_destino}</CampoLectura>
                        <CampoLectura etiqueta="CC">{invitacion.correo_cc ?? 'Sin copia'}</CampoLectura>
                        <CampoLectura etiqueta="Generada">{fechaHora(invitacion.creado_en)}</CampoLectura>
                        <CampoLectura etiqueta="Enviada">{fechaHora(invitacion.enviado_en)}</CampoLectura>
                        <CampoLectura etiqueta="Expira">{fechaHora(invitacion.expira_en)}</CampoLectura>
                        {invitacion.utilizado_en && <><CampoLectura etiqueta="Utilizada">{fechaHora(invitacion.utilizado_en)}</CampoLectura></>}
                        {invitacion.revocado_en && <><CampoLectura etiqueta="Revocada">{fechaHora(invitacion.revocado_en)}</CampoLectura></>}
                      </DetalleCampos>
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
    <div className="detalle-secciones">
      <LineaTiempoConvenio convenioId={convenioId} />
      <VersionesConvenio convenioId={convenioId} />
      <TrazabilidadRevisiones convenioId={convenioId} solicitudId={solicitudId} />
    </div>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { enumLabel } from '../components/tableFormatters'
import { CampoLectura, DetalleCampos } from '../components/DetalleCampos'
import { apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { DocumentoPreviewModal } from '../components/DocumentoPreviewModal'
import type { Convenio } from './epica02'
import { type SolicitudRecibida, useSolicitudRecibida } from './solicitudes'
import { accionConvenioSolicitud } from './accionConvenioSolicitud'
import './gestorConvenios.css'

function valor(dato: string | null | undefined) {
  return dato || '—'
}

export function SolicitudRecibidaPage() {
  const params = useParams()
  const id = params.solicitudId ? Number(params.solicitudId) : null
  const consulta = useSolicitudRecibida(id)
  const navigate = useNavigate()
  const notify = useNotifications()
  const { puede } = useSesion()

  const iniciarElaboracion = useMutation({
    mutationFn: () => apiFetch<Convenio>(`/solicitudes/recibidas/${id}/iniciar-elaboracion`, { method: 'POST' }),
    onSuccess: (convenio) => {
      notify({ type: 'success', message: 'Elaboración iniciada' })
      navigate(`/convenios/${convenio.id}/elaboracion`)
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })

  const cliente = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const [observacionesDevolucion, setObservacionesDevolucion] = useState('')
  const [rechazando, setRechazando] = useState(false)
  const [devolviendo, setDevolviendo] = useState(false)
  const [documentoPreview, setDocumentoPreview] = useState<{
    nombre: string
    urlContenido: string
    urlDescarga?: string
    tipoMime?: string
  } | null>(null)
  const refrescar = async (actualizada: SolicitudRecibida) => {
    cliente.setQueryData(['solicitudes', 'recibidas', actualizada.id], actualizada)
    await cliente.invalidateQueries({ queryKey: ['solicitudes', 'recibidas'] })
    await cliente.invalidateQueries({ queryKey: ['solicitudes', 'mias'] })
    await cliente.invalidateQueries({ queryKey: ['solicitudes', actualizada.id] })
  }
  const aceptar = useMutation({
    mutationFn: () => apiFetch<SolicitudRecibida>(`/solicitudes/recibidas/${id}/aceptar`, { method: 'POST' }),
    onSuccess: async (actualizada) => {
      await refrescar(actualizada)
      notify({ type: 'success', message: 'Solicitud aprobada' })
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })
  const rechazar = useMutation({
    mutationFn: () => apiFetch<SolicitudRecibida>(`/solicitudes/recibidas/${id}/rechazar`, { method: 'POST', body: JSON.stringify({ motivo }) }),
    onSuccess: async (actualizada) => {
      await refrescar(actualizada)
      setRechazando(false)
      notify({ type: 'success', message: 'Solicitud rechazada' })
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })
  const devolver = useMutation({
    mutationFn: () => apiFetch<SolicitudRecibida>(`/solicitudes/recibidas/${id}/devolver`, { method: 'POST', body: JSON.stringify({ observaciones: observacionesDevolucion }) }),
    onSuccess: async (actualizada) => {
      await refrescar(actualizada)
      setDevolviendo(false)
      notify({ type: 'success', message: 'Solicitud devuelta con observaciones' })
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })

  if (consulta.isPending) return <p className="estado-pagina">Cargando solicitud…</p>
  if (consulta.isError) return <p className="alert-error">{consulta.error.message}</p>
  const solicitud = consulta.data
  if (!solicitud) return null
  const pendiente = ['RADICADA', 'EN_ESTUDIO'].includes(solicitud.estado)
  const gestiona = puede('solicitudes.gestionar_recibidas')
  const ocupado = aceptar.isPending || rechazar.isPending || devolver.isPending
  const accionConvenio = accionConvenioSolicitud(solicitud, puede)

  return (
    <div className="solicitud-recibida detalle-secciones">
      <section className="header-banner">
        <h1>{solicitud.consecutivo}</h1>
        <p><span className="badge">{solicitud.estado.replaceAll('_', ' ')}</span> · Radicada {solicitud.fecha_radicacion ? new Date(solicitud.fecha_radicacion).toLocaleString() : '—'}</p>
      </section>

      <section className="card"><h2>Información del solicitante</h2><DetalleCampos>
        <CampoLectura etiqueta="Nombre">{valor(solicitud.solicitante_nombre)}</CampoLectura><CampoLectura etiqueta="Correo">{valor(solicitud.solicitante_correo)}</CampoLectura>
        <CampoLectura etiqueta="Tipo de solicitante">{enumLabel(solicitud.tipo_solicitante)}</CampoLectura><CampoLectura etiqueta="Documento">{valor(solicitud.solicitante_documento)}</CampoLectura>
        <CampoLectura etiqueta="Cargo">{valor(solicitud.solicitante_cargo)}</CampoLectura>
        <CampoLectura etiqueta="Entidad">{valor(solicitud.solicitante_entidad)}</CampoLectura>
        <CampoLectura etiqueta="Unidad">{valor(solicitud.solicitante_unidad)}</CampoLectura>
        <CampoLectura etiqueta="Programa">{valor(solicitud.solicitante_programa)}</CampoLectura>
      </DetalleCampos></section>

      <section className="card"><h2>Contraparte propuesta y contacto</h2><div className="detalle-grupo"><h3>Institución propuesta</h3><DetalleCampos>
        <CampoLectura etiqueta="Nombre">{valor(solicitud.nombre_aliado_propuesto)}</CampoLectura><CampoLectura etiqueta="Identificación">{valor(solicitud.identificacion_aliado_propuesto)}</CampoLectura>
        <CampoLectura etiqueta="Tipo">{solicitud.tipo_aliado_propuesto ? enumLabel(solicitud.tipo_aliado_propuesto) : valor(null)}</CampoLectura>
        <CampoLectura etiqueta="País">{valor(solicitud.pais_aliado_propuesto)}</CampoLectura>
        <CampoLectura etiqueta="Ciudad">{valor(solicitud.ciudad_aliado_propuesto)}</CampoLectura>
        <CampoLectura etiqueta="Correo institucional">{valor(solicitud.correo_aliado_propuesto)}</CampoLectura><CampoLectura etiqueta="Teléfono institucional">{valor(solicitud.telefono_aliado_propuesto)}</CampoLectura>
        <CampoLectura etiqueta="Dirección">{valor(solicitud.direccion_aliado_propuesto)}</CampoLectura><CampoLectura etiqueta="Sector económico">{valor(solicitud.sector_economico_aliado_propuesto)}</CampoLectura>
        </DetalleCampos></div><div className="detalle-grupo"><h3>Contacto de la contraparte</h3><DetalleCampos><CampoLectura etiqueta="Nombre">{valor(solicitud.contacto_contraparte_nombre)}</CampoLectura><CampoLectura etiqueta="Cargo">{valor(solicitud.contacto_contraparte_cargo)}</CampoLectura>
        <CampoLectura etiqueta="Correo">{valor(solicitud.contacto_contraparte_correo)}</CampoLectura><CampoLectura etiqueta="Teléfono">{valor(solicitud.contacto_contraparte_telefono)}</CampoLectura>
      </DetalleCampos></div></section>

      <section className="card"><h2>Convenio solicitado</h2><DetalleCampos>
        <CampoLectura etiqueta="Tipo de convenio">{valor(solicitud.tipo_convenio_nombre)}</CampoLectura><CampoLectura etiqueta="Objeto" amplio>{valor(solicitud.objeto)}</CampoLectura>
        <CampoLectura etiqueta="Justificación" amplio>{valor(solicitud.justificacion)}</CampoLectura><CampoLectura etiqueta="Implicación financiera" amplio>{valor(solicitud.implicacion_financiera)}</CampoLectura>
        <CampoLectura etiqueta="Actividades" amplio>{valor(solicitud.actividades_por_parte)}</CampoLectura><CampoLectura etiqueta="Metas" amplio>{valor(solicitud.metas_esperadas)}</CampoLectura>
        <CampoLectura etiqueta="Vigencia estimada">{valor(solicitud.vigencia_estimada)}</CampoLectura><CampoLectura etiqueta="Requisitos de renovación" amplio>{valor(solicitud.requisitos_renovacion)}</CampoLectura>
        <CampoLectura etiqueta="Observaciones del solicitante" amplio>{valor(solicitud.observaciones)}</CampoLectura>
      </DetalleCampos></section>

      <section className="card"><h2>Supervisores</h2>
        <div className="detalle-grupo"><h3>Supervisor de la USB</h3><DetalleCampos>
          <CampoLectura etiqueta="Nombre">{valor(solicitud.supervisor_usb_nombre)}</CampoLectura>
          <CampoLectura etiqueta="Cargo">{valor(solicitud.supervisor_usb_cargo)}</CampoLectura>
          <CampoLectura etiqueta="Correo">{valor(solicitud.supervisor_usb_correo)}</CampoLectura>
          <CampoLectura etiqueta="Teléfono">{valor(solicitud.supervisor_usb_telefono)}</CampoLectura>
        </DetalleCampos></div>
        <div className="detalle-grupo"><h3>Supervisor de la contraparte</h3><DetalleCampos>
          <CampoLectura etiqueta="Nombre">{valor(solicitud.supervisor_contraparte_nombre)}</CampoLectura>
          <CampoLectura etiqueta="Cargo">{valor(solicitud.supervisor_contraparte_cargo)}</CampoLectura>
          <CampoLectura etiqueta="Correo">{valor(solicitud.supervisor_contraparte_correo)}</CampoLectura>
          <CampoLectura etiqueta="Teléfono">{valor(solicitud.supervisor_contraparte_telefono)}</CampoLectura>
        </DetalleCampos></div>
      </section>

      <section className="card">
        <h2>Documentos adjuntos</h2>
        {solicitud.documentos.length === 0 ? (
          <p>No hay documentos adjuntos.</p>
        ) : (
          <ul className="solicitud-documentos-lista">
            {solicitud.documentos.map((documento) => (
              <li key={documento.id} className="solicitud-documento-item">
                <div className="solicitud-documento-info">
                  <a
                    href={`/api/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=inline`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(evento) => {
                      evento.preventDefault()
                      setDocumentoPreview({
                        nombre: documento.nombre_original,
                        urlContenido: `/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=inline`,
                        urlDescarga: `/api/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=attachment`,
                        tipoMime: documento.tipo_mime,
                      })
                    }}
                  >
                    {documento.nombre_original}
                  </a>{' '}
                  <span className="badge">{documento.tipo_documento}</span>
                </div>
                <div className="solicitud-documento-acciones">
                  <button
                    type="button"
                    className="btn btn-outline btn-small"
                    onClick={() =>
                      setDocumentoPreview({
                        nombre: documento.nombre_original,
                        urlContenido: `/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=inline`,
                        urlDescarga: `/api/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=attachment`,
                        tipoMime: documento.tipo_mime,
                      })
                    }
                  >
                    Previsualizar
                  </button>
                  <a
                    className="btn btn-outline btn-small"
                    href={`/api/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido?disposicion=attachment`}
                    download={documento.nombre_original}
                  >
                    Descargar
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {solicitud.fecha_decision && (
        <section className="card"><h2>Decisión ORI</h2><DetalleCampos>
          <CampoLectura etiqueta="Resultado">{solicitud.estado === 'RECHAZADA' ? 'Rechazada' : solicitud.estado === 'DEVUELTA' ? 'Devuelta' : 'Aprobada'}</CampoLectura>
          <CampoLectura etiqueta="Responsable">{valor(solicitud.decidida_por_nombre)}</CampoLectura>
          <CampoLectura etiqueta="Fecha y hora">{new Date(solicitud.fecha_decision).toLocaleString()}</CampoLectura>
          {solicitud.estado === 'RECHAZADA' && solicitud.motivo_rechazo && <><CampoLectura etiqueta="Motivo del rechazo" amplio>{solicitud.motivo_rechazo}</CampoLectura></>}
          {solicitud.estado === 'DEVUELTA' && solicitud.observaciones_devolucion && <><CampoLectura etiqueta="Observaciones de devolución">{solicitud.observaciones_devolucion}</CampoLectura></>}
        </DetalleCampos></section>
      )}

      {solicitud.estado !== 'DEVUELTA' && solicitud.observaciones_devolucion && (
        <section className="card"><h2>Observaciones de devolución anterior</h2>
          <p className="detalle-texto">{solicitud.observaciones_devolucion}</p>
        </section>
      )}

      {pendiente && gestiona && rechazando && (
        <section className="card"><h2>Rechazar solicitud</h2>
          <label className="form-group" htmlFor="motivo-rechazo"><span className="form-label">Motivo del rechazo *</span>
            <textarea id="motivo-rechazo" className="form-control" value={motivo} maxLength={2000} onChange={(evento) => setMotivo(evento.target.value)} required /></label>
          <div className="page-toolbar">
            <button className="btn btn-outline" type="button" disabled={ocupado} onClick={() => setRechazando(false)}>Cancelar</button>
            <button className="btn btn-danger" type="button" disabled={!motivo.trim() || ocupado} onClick={() => rechazar.mutate()}>Confirmar rechazo</button>
          </div>
        </section>
      )}

      {pendiente && gestiona && devolviendo && (
        <section className="card"><h2>Devolver solicitud</h2>
          <label className="form-group" htmlFor="observaciones-devolucion"><span className="form-label">Observaciones de devolución *</span>
            <textarea id="observaciones-devolucion" className="form-control" value={observacionesDevolucion} maxLength={2000} onChange={(evento) => setObservacionesDevolucion(evento.target.value)} required /></label>
          <div className="page-toolbar">
            <button className="btn btn-outline" type="button" disabled={ocupado} onClick={() => setDevolviendo(false)}>Cancelar</button>
            <button className="btn btn-primary" type="button" disabled={!observacionesDevolucion.trim() || ocupado} onClick={() => devolver.mutate()}>Confirmar devolución</button>
          </div>
        </section>
      )}

      <div className="page-toolbar">
        <Link className="btn btn-outline" to="/ori/solicitudes">Volver</Link>
        <Link className="btn btn-outline" to={`/ori/solicitudes/${solicitud.id}/historial`}>Ver historial</Link>
        {pendiente && gestiona && !rechazando && !devolviendo && <>
          <button className="btn btn-danger" type="button" disabled={ocupado} onClick={() => setRechazando(true)}>Rechazar</button>
          <button className="btn btn-outline" type="button" disabled={ocupado} onClick={() => setDevolviendo(true)}>Devolver</button>
          <button className="btn btn-primary" type="button" disabled={ocupado} onClick={() => window.confirm('¿Confirma que aprueba esta solicitud?') && aceptar.mutate()}>Aprobar</button>
        </>}
        {accionConvenio && (solicitud.convenio_id
          ? <Link className="btn btn-primary" to={accionConvenio.to}>{accionConvenio.texto}</Link>
          : <button className="btn btn-primary" type="button" disabled={iniciarElaboracion.isPending} onClick={() => iniciarElaboracion.mutate()}>{accionConvenio.texto}</button>)}
      </div>

      {documentoPreview && (
        <DocumentoPreviewModal
          nombreArchivo={documentoPreview.nombre}
          urlContenido={documentoPreview.urlContenido}
          urlDescarga={documentoPreview.urlDescarga}
          tipoMime={documentoPreview.tipoMime}
          onCerrar={() => setDocumentoPreview(null)}
        />
      )}
    </div>
  )
}

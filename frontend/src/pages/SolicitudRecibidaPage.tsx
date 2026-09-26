import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { apiFetch } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import type { Convenio } from './epica02'
import { useSolicitudRecibida } from './solicitudes'

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
  const [rechazando, setRechazando] = useState(false)
  const refrescar = () => cliente.invalidateQueries({ queryKey: ['solicitudes', 'recibidas'] })
  const aceptar = useMutation({
    mutationFn: () => apiFetch(`/solicitudes/recibidas/${id}/aceptar`, { method: 'POST' }),
    onSuccess: async () => {
      await refrescar()
      notify({ type: 'success', message: 'Solicitud aceptada' })
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })
  const rechazar = useMutation({
    mutationFn: () => apiFetch(`/solicitudes/recibidas/${id}/rechazar`, { method: 'POST', body: JSON.stringify({ motivo }) }),
    onSuccess: async () => {
      await refrescar()
      setRechazando(false)
      notify({ type: 'success', message: 'Solicitud rechazada' })
    },
    onError: (error: Error) => notify({ type: 'error', message: error.message }),
  })

  if (consulta.isPending) return <p className="estado-pagina">Cargando solicitud…</p>
  if (consulta.isError) return <p className="alert-error">{consulta.error.message}</p>
  const solicitud = consulta.data
  if (!solicitud) return null
  const pendiente = ['RADICADA', 'EN_ESTUDIO'].includes(solicitud.estado)
  const gestiona = puede('solicitudes.gestionar_recibidas')
  const ocupado = aceptar.isPending || rechazar.isPending

  return (
    <>
      <section className="header-banner">
        <h1>{solicitud.consecutivo}</h1>
        <p><span className="badge">{solicitud.estado.replaceAll('_', ' ')}</span> · Radicada {solicitud.fecha_radicacion ? new Date(solicitud.fecha_radicacion).toLocaleString() : '—'}</p>
      </section>

      <section className="card"><h2>Información del solicitante</h2><dl>
        <dt>Nombre</dt><dd>{valor(solicitud.solicitante_nombre)}</dd><dt>Correo</dt><dd>{valor(solicitud.solicitante_correo)}</dd>
        <dt>Tipo</dt><dd>{solicitud.tipo_solicitante}</dd><dt>Documento</dt><dd>{valor(solicitud.solicitante_documento)}</dd>
        <dt>Cargo</dt><dd>{valor(solicitud.solicitante_cargo)}</dd><dt>Entidad / Unidad / Programa</dt><dd>{[solicitud.solicitante_entidad, solicitud.solicitante_unidad, solicitud.solicitante_programa].filter(Boolean).join(' / ') || '—'}</dd>
      </dl></section>

      <section className="card"><h2>Contraparte propuesta y contacto</h2><dl>
        <dt>Nombre</dt><dd>{valor(solicitud.nombre_aliado_propuesto)}</dd><dt>Identificación</dt><dd>{valor(solicitud.identificacion_aliado_propuesto)}</dd>
        <dt>Tipo</dt><dd>{valor(solicitud.tipo_aliado_propuesto)}</dd><dt>Ubicación</dt><dd>{[solicitud.pais_aliado_propuesto, solicitud.ciudad_aliado_propuesto].filter(Boolean).join(' / ') || '—'}</dd>
        <dt>Correo institucional</dt><dd>{valor(solicitud.correo_aliado_propuesto)}</dd><dt>Teléfono institucional</dt><dd>{valor(solicitud.telefono_aliado_propuesto)}</dd>
        <dt>Dirección</dt><dd>{valor(solicitud.direccion_aliado_propuesto)}</dd><dt>Sector económico</dt><dd>{valor(solicitud.sector_economico_aliado_propuesto)}</dd>
        <dt>Contacto</dt><dd>{valor(solicitud.contacto_contraparte_nombre)}</dd><dt>Cargo</dt><dd>{valor(solicitud.contacto_contraparte_cargo)}</dd>
        <dt>Correo</dt><dd>{valor(solicitud.contacto_contraparte_correo)}</dd><dt>Teléfono</dt><dd>{valor(solicitud.contacto_contraparte_telefono)}</dd>
      </dl></section>

      <section className="card"><h2>Convenio solicitado</h2><dl>
        <dt>Tipo de convenio</dt><dd>{valor(solicitud.tipo_convenio_nombre)}</dd><dt>Objeto</dt><dd>{valor(solicitud.objeto)}</dd>
        <dt>Justificación</dt><dd>{valor(solicitud.justificacion)}</dd><dt>Implicación financiera</dt><dd>{valor(solicitud.implicacion_financiera)}</dd>
        <dt>Actividades</dt><dd>{valor(solicitud.actividades_por_parte)}</dd><dt>Metas</dt><dd>{valor(solicitud.metas_esperadas)}</dd>
        <dt>Vigencia estimada</dt><dd>{valor(solicitud.vigencia_estimada)}</dd><dt>Requisitos de renovación</dt><dd>{valor(solicitud.requisitos_renovacion)}</dd>
        <dt>Observaciones originales</dt><dd>{valor(solicitud.observaciones)}</dd>
      </dl></section>

      <section className="card"><h2>Supervisores</h2><dl>
        <dt>Supervisor USB</dt><dd>{[solicitud.supervisor_usb_nombre, solicitud.supervisor_usb_cargo, solicitud.supervisor_usb_correo, solicitud.supervisor_usb_telefono].filter(Boolean).join(' · ') || '—'}</dd>
        <dt>Supervisor contraparte</dt><dd>{[solicitud.supervisor_contraparte_nombre, solicitud.supervisor_contraparte_cargo, solicitud.supervisor_contraparte_correo, solicitud.supervisor_contraparte_telefono].filter(Boolean).join(' · ') || '—'}</dd>
      </dl></section>

      <section className="card"><h2>Documentos adjuntos</h2>
        {solicitud.documentos.length === 0 ? <p>No hay documentos adjuntos.</p> : <ul>{solicitud.documentos.map((documento) => <li key={documento.id}><a href={`/api/solicitudes/recibidas/${solicitud.id}/documentos/${documento.id}/contenido`} target="_blank" rel="noreferrer">{documento.nombre_original}</a> <span className="badge">{documento.tipo_documento}</span></li>)}</ul>}
      </section>

      {solicitud.fecha_decision && (
        <section className="card"><h2>Decisión ORI</h2><dl>
          <dt>Resultado</dt><dd>{solicitud.estado === 'RECHAZADA' ? 'Rechazada' : 'Aceptada'}</dd>
          <dt>Responsable</dt><dd>{valor(solicitud.decidida_por_nombre)}</dd>
          <dt>Fecha y hora</dt><dd>{new Date(solicitud.fecha_decision).toLocaleString()}</dd>
          {solicitud.motivo_rechazo && <><dt>Motivo del rechazo</dt><dd>{solicitud.motivo_rechazo}</dd></>}
        </dl></section>
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

      <div className="page-toolbar">
        <Link className="btn btn-outline" to="/ori/solicitudes">Volver</Link>
        {pendiente && gestiona && !rechazando && <>
          <button className="btn btn-danger" type="button" disabled={ocupado} onClick={() => setRechazando(true)}>Rechazar</button>
          <button className="btn btn-primary" type="button" disabled={ocupado} onClick={() => window.confirm('¿Confirma que acepta esta solicitud?') && aceptar.mutate()}>Aceptar</button>
        </>}
        {solicitud.estado === 'APROBADA' && solicitud.convenio_id && gestiona && <Link className="btn btn-primary" to={`/convenios/${solicitud.convenio_id}/elaboracion`}>Continuar elaboración</Link>}
        {solicitud.estado === 'APROBADA' && !solicitud.convenio_id && gestiona && <button className="btn btn-primary" type="button" disabled={iniciarElaboracion.isPending} onClick={() => iniciarElaboracion.mutate()}>Iniciar elaboración</button>}
      </div>
    </>
  )
}

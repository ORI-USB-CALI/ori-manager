import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'
import type { EstadoSolicitud, SolicitudRecibida } from './solicitudes'

const ESTADOS: EstadoSolicitud[] = ['RADICADA', 'EN_ESTUDIO', 'APROBADA', 'DEVUELTA', 'RECHAZADA']

export function SolicitudesRecibidasPage() {
  const [estado, setEstado] = useState<EstadoSolicitud | ''>('')
  const consulta = useQuery({
    queryKey: ['solicitudes', 'recibidas'],
    queryFn: () => apiFetch<{ items: SolicitudRecibida[]; total: number }>('/solicitudes/recibidas'),
    retry: false,
  })
  const items = consulta.data?.items.filter((item) => !estado || item.estado === estado) ?? []

  return (
    <>
      <section className="header-banner">
        <h1>Solicitudes recibidas</h1>
        <p>Bandeja operativa de solicitudes radicadas ante la ORI.</p>
      </section>
      <div className="page-toolbar">
        <label className="form-group" htmlFor="filtro-estado">
          <span className="form-label">Estado</span>
          <select id="filtro-estado" className="form-control select" value={estado} onChange={(event) => setEstado(event.target.value as EstadoSolicitud | '')}>
            <option value="">Todos</option>
            {ESTADOS.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
      </div>
      {consulta.isPending && <p className="estado-pagina">Cargando solicitudes recibidas…</p>}
      {consulta.isError && <p className="alert-error">{consulta.error.message}</p>}
      {consulta.data && items.length === 0 && <section className="card estado-vacio"><p>No hay solicitudes para el filtro seleccionado.</p></section>}
      {items.length > 0 && (
        <div className="table-container">
          <table>
            <thead><tr><th>Consecutivo</th><th>Solicitante</th><th>Tipo</th><th>Contraparte propuesta</th><th>Tipo de convenio</th><th>Radicación</th><th>Estado</th><th>Acción</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.consecutivo}</td>
                  <td>{item.solicitante_nombre ?? item.solicitante_correo ?? '—'}</td>
                  <td>{item.tipo_solicitante}</td>
                  <td>{item.nombre_aliado_propuesto ?? '—'}</td>
                  <td>{item.tipo_convenio_nombre ?? '—'}</td>
                  <td>{item.fecha_radicacion ? new Date(item.fecha_radicacion).toLocaleString() : '—'}</td>
                  <td><span className="badge">{item.estado.replaceAll('_', ' ')}</span></td>
                  <td><Link to={`/ori/solicitudes/${item.id}`}>Revisar</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

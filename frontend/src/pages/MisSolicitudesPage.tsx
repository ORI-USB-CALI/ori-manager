import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'
import type { Solicitud } from './solicitudes'

export function MisSolicitudesPage() {
  const consulta = useQuery({
    queryKey: ['solicitudes', 'mias'],
    queryFn: () => apiFetch<{ items: Solicitud[]; total: number }>('/solicitudes/mias'),
    retry: false,
  })

  return (
    <>
      <section className="header-banner"><h1>Mis solicitudes</h1><p>Consulte sus borradores y solicitudes radicadas.</p></section>
      <div className="page-toolbar"><Link className="btn btn-primary" to="/solicitudes/nueva">Nueva solicitud</Link></div>
      {consulta.isPending && <p className="estado-pagina">Cargando solicitudes…</p>}
      {consulta.isError && <p className="alert-error">{consulta.error.message}</p>}
      {consulta.data && consulta.data.items.length === 0 && <section className="card estado-vacio"><p>Aún no tiene solicitudes.</p></section>}
      {consulta.data && consulta.data.items.length > 0 && (
        <div className="table-container"><table><thead><tr><th>Consecutivo</th><th>Contraparte</th><th>Estado</th><th>Radicación</th><th /></tr></thead><tbody>
          {consulta.data.items.map((item) => <tr key={item.id}><td>{item.consecutivo}</td><td>{item.nombre_aliado_propuesto ?? 'Sin diligenciar'}</td><td><span className="badge">{item.estado}</span></td><td>{item.fecha_radicacion ? new Date(item.fecha_radicacion).toLocaleString() : '—'}</td><td><Link to={`/solicitudes/${item.id}`}>{item.estado === 'BORRADOR' ? 'Continuar' : 'Ver'}</Link></td></tr>)}
        </tbody></table></div>
      )}
    </>
  )
}

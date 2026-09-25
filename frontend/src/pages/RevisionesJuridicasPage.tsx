import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'

interface RevisionJuridicaPendiente {
  revision_id: number
  convenio_id: number
  codigo_convenio: string | null
  solicitud_consecutivo: string
  objeto: string | null
  tipo_convenio: { id: number; nombre: string } | null
  responsable: { id: number; nombre_completo: string; correo: string }
  fecha_recepcion: string
}

export function RevisionesJuridicasPage() {
  const consulta = useQuery({
    queryKey: ['revisiones-juridicas', 'pendientes'],
    queryFn: () => apiFetch<RevisionJuridicaPendiente[]>('/convenios/revisiones-juridicas/pendientes'),
    retry: false,
  })

  return (
    <>
      <section className="header-banner">
        <h1>Revisiones jurídicas</h1>
        <p>Convenios pendientes de revisión y aval jurídico.</p>
      </section>
      {consulta.isPending && <p className="estado-pagina">Cargando revisiones jurídicas…</p>}
      {consulta.isError && <p className="alert-error">{consulta.error.message}</p>}
      {consulta.data?.length === 0 && <section className="card estado-vacio"><p>No hay revisiones jurídicas pendientes.</p></section>}
      {consulta.data && consulta.data.length > 0 && (
        <div className="table-container">
          <table>
            <thead><tr><th>Convenio</th><th>Solicitud origen</th><th>Objeto</th><th>Tipo</th><th>Responsable</th><th>Fecha de recepción</th><th>Acción</th></tr></thead>
            <tbody>{consulta.data.map((revision) => (
              <tr key={revision.revision_id}>
                <td>{revision.codigo_convenio ?? `#${revision.convenio_id}`}</td>
                <td>{revision.solicitud_consecutivo}</td>
                <td>{revision.objeto ?? '—'}</td>
                <td>{revision.tipo_convenio?.nombre ?? '—'}</td>
                <td>{revision.responsable.nombre_completo}</td>
                <td>{new Date(revision.fecha_recepcion).toLocaleString()}</td>
                <td><Link className="btn btn-primary btn-small" to={`/convenios/${revision.convenio_id}`}>Revisar</Link></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>
  )
}

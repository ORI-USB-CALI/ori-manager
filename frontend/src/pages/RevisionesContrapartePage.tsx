import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { ApiError } from '../app/api'
import { CLAVE_REVISIONES_CONTRAPARTE, obtenerRevisionesContraparte } from './revisionContraparte'

function fecha(valor: string) {
  return new Date(valor).toLocaleString()
}

export function RevisionesContrapartePage() {
  const consulta = useQuery({
    queryKey: CLAVE_REVISIONES_CONTRAPARTE,
    queryFn: obtenerRevisionesContraparte,
    retry: false,
  })

  if (consulta.isPending) return <p className="estado-pagina">Cargando revisiones de contraparte…</p>
  if (consulta.isError) {
    return (
      <section className="card estado-vacio">
        <h1>No se pudieron consultar las revisiones</h1>
        <p>{consulta.error instanceof ApiError ? consulta.error.message : 'Intenta nuevamente.'}</p>
      </section>
    )
  }

  return (
    <>
      <section className="header-banner">
        <h1>Revisiones de contraparte</h1>
        <p>Elaboraciones de convenio que requieren tu revisión como Solicitante.</p>
      </section>
      {consulta.data.length === 0 ? (
        <section className="card estado-vacio">
          <h2>No tienes revisiones pendientes</h2>
          <p>Cuando la ORI envíe una elaboración, aparecerá aquí de forma persistente.</p>
        </section>
      ) : (
        <section className="card">
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Convenio</th><th>Objeto</th><th>Versión</th><th>Enviado por</th><th>Fecha</th><th /></tr></thead>
              <tbody>
                {consulta.data.map((revision) => (
                  <tr key={revision.revision_id}>
                    <td>{revision.codigo_convenio ?? `#${revision.convenio_id}`}</td>
                    <td>{revision.objeto ?? '—'}</td>
                    <td>V{revision.version_numero}</td>
                    <td>{revision.enviada_por.nombre_completo}</td>
                    <td>{fecha(revision.fecha_envio)}</td>
                    <td><Link className="btn btn-outline btn-small" to={`/revisiones-contraparte/${revision.revision_id}`}>Revisar</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}

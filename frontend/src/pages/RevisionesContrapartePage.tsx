import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { ApiError } from '../app/api'
import { DataTable, type DataTableColumn } from '../components/DataTable'
import { referenciaConvenio } from './epica02'
import { CLAVE_REVISIONES_CONTRAPARTE, obtenerRevisionesContraparte, type RevisionContrapartePendiente } from './revisionContraparte'

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

  const columnas: DataTableColumn<RevisionContrapartePendiente>[] = [
    { id: 'convenio', header: 'Convenio', className: 'tabla-col-referencia', render: (revision) => referenciaConvenio(revision.codigo_convenio, revision.convenio_id) },
    { id: 'objeto', header: 'Objeto', className: 'tabla-col-descripcion', render: (revision) => revision.objeto ?? '—' },
    { id: 'version', header: 'Versión', className: 'tabla-col-numero', render: (revision) => `V${revision.version_numero}` },
    { id: 'autor', header: 'Enviado por', className: 'tabla-col-persona', render: (revision) => revision.enviada_por.nombre_completo },
    { id: 'fecha', header: 'Fecha', className: 'tabla-col-fecha', render: (revision) => fecha(revision.fecha_envio) },
    { id: 'acciones', header: 'Acciones', className: 'tabla-col-acciones', render: (revision) => <Link className="btn btn-outline btn-small" to={`/revisiones-contraparte/${revision.revision_id}`}>Revisar</Link> },
  ]

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
        <DataTable columns={columnas} rows={consulta.data} rowKey={(revision) => revision.revision_id}
          label="Revisiones de contraparte" tableClassName="tabla-densa" containerClassName="tabla-densa-region" />
      )}
    </>
  )
}

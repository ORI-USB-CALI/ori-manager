import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { type Convenio } from './epica02'

function fecha(valor: string | null) {
  return valor ? new Date(valor).toLocaleDateString() : '—'
}

export function ConvenioDetallePage() {
  const { convenioId } = useParams()
  const id = Number(convenioId)
  const convenio = useQuery({
    queryKey: ['convenio', id],
    queryFn: () => apiFetch<Convenio>(`/convenios/${id}`),
    enabled: Number.isInteger(id),
    retry: false,
  })
  if (convenio.isPending) return <p className="estado-pagina">Cargando convenio…</p>
  if (convenio.isError) return <section className="card estado-vacio"><h1>{convenio.error instanceof ApiError && convenio.error.status === 404 ? 'Convenio no encontrado' : 'No se pudo consultar el convenio'}</h1></section>
  if (!convenio.data) return null
  const datos = convenio.data
  return (
    <>
      <section className="header-banner"><h1>Convenio {datos.codigo ?? `#${datos.id}`}</h1><p><span className="badge">{datos.estado}</span></p></section>
      <div className="page-toolbar"><Link className="btn btn-primary" to={`/convenios/${datos.id}/elaboracion`}>Ir a Elaboración</Link></div>
      <section className="card"><h2>Información base</h2><dl><dt>Solicitud</dt><dd>#{datos.solicitud_id}</dd><dt>Objeto</dt><dd>{datos.objeto ?? '—'}</dd><dt>Alcance</dt><dd>{datos.alcance ?? '—'}</dd><dt>Aliado</dt><dd>{datos.aliado ? <Link to={`/aliados/${datos.aliado.id}`}>{datos.aliado.nombre}</Link> : 'Sin aliado asociado'}</dd><dt>Responsable</dt><dd>{datos.creado_por.nombre_completo} ({datos.creado_por.correo})</dd><dt>Fecha de creación</dt><dd>{fecha(datos.creado_en)}</dd></dl></section>
    </>
  )
}

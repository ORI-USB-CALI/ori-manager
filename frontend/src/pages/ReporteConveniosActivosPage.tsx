import { Link } from 'react-router-dom'

import { useSesion } from '../auth/sesion'
import { referenciaConvenio } from './epica02'
import {
  URL_DESCARGA_REPORTE_EXCEL,
  URL_DESCARGA_REPORTE_PDF,
  useReporteConveniosActivos,
  type ConvenioReporteActivo,
} from './reportes'

function identificacion(convenio: ConvenioReporteActivo): string {
  return referenciaConvenio(convenio.codigo, convenio.id)
}

function formatearFecha(fecha: string | null): string {
  if (!fecha) return 'Sin fecha registrada'
  return new Date(`${fecha}T00:00:00Z`).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function varianteEstado(estado: string): string {
  if (estado === 'VIGENTE') return 'success'
  if (estado === 'POR_VENCER') return 'warning'
  if (estado === 'VENCIDO') return 'danger'
  return 'neutral'
}

function textoActividades(convenio: ConvenioReporteActivo): string {
  if (convenio.actividades.length === 0) return 'Sin actividades registradas'
  return `${convenio.actividades.length} registrada(s)`
}

export function ReporteConveniosActivosPage() {
  const { puede } = useSesion()
  const autorizado = puede('convenios.ver_reportes')
  const reporte = useReporteConveniosActivos(autorizado)

  if (!autorizado) return null

  const convenios = reporte.data ?? []
  const descargasDeshabilitadas = reporte.isPending || reporte.isError

  return (
    <>
      <section className="header-banner">
        <h1>Reporte de convenios activos</h1>
        <p>
          Información consolidada de los convenios vigentes y por vencer, con sus
          actividades registradas durante la vigencia.
        </p>
      </section>

      <div className="page-toolbar">
        {descargasDeshabilitadas ? (
          <>
            <button type="button" className="btn btn-outline" disabled>
              Descargar PDF
            </button>
            <button type="button" className="btn btn-outline" disabled>
              Descargar Excel
            </button>
          </>
        ) : (
          <>
            <a className="btn btn-outline" href={URL_DESCARGA_REPORTE_PDF}>
              Descargar PDF
            </a>
            <a className="btn btn-outline" href={URL_DESCARGA_REPORTE_EXCEL}>
              Descargar Excel
            </a>
          </>
        )}
        <button
          type="button"
          className="btn btn-outline btn-small"
          disabled={reporte.isFetching}
          onClick={() => {
            void reporte.refetch()
          }}
        >
          {reporte.isFetching ? 'Actualizando…' : 'Actualizar'}
        </button>
      </div>

      {reporte.isPending && (
        <p className="estado-pagina" role="status">Cargando convenios activos…</p>
      )}
      {reporte.isError && (
        <section className="alert-error" role="alert">
          <p>No se pudo consultar el reporte de convenios activos.</p>
          <button
            className="btn btn-outline btn-small"
            type="button"
            disabled={reporte.isFetching}
            onClick={() => {
              void reporte.refetch()
            }}
          >
            {reporte.isFetching ? 'Consultando…' : 'Reintentar'}
          </button>
        </section>
      )}

      {!reporte.isPending && !reporte.isError && convenios.length === 0 && (
        <div className="card estado-vacio">
          <p>No hay convenios activos para mostrar.</p>
        </div>
      )}

      {!reporte.isPending && !reporte.isError && convenios.length > 0 && (
        <div
          className="table-container"
          role="region"
          aria-label="Tabla de convenios activos"
          tabIndex={0}
        >
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Convenio</th>
                <th scope="col">Aliado</th>
                <th scope="col">Tipo</th>
                <th scope="col">Unidad</th>
                <th scope="col">Registrado por</th>
                <th scope="col">Vigencia</th>
                <th scope="col">Estado</th>
                <th scope="col">Actividades</th>
                <th scope="col">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {convenios.map((convenio) => (
                <tr key={convenio.id}>
                  <th scope="row">
                    {identificacion(convenio)}
                    {convenio.objeto && (
                      <small className="tabla-ayuda" title={convenio.objeto}>
                        {convenio.objeto}
                      </small>
                    )}
                  </th>
                  <td>{convenio.aliado ?? 'Sin aliado registrado'}</td>
                  <td>{convenio.tipo_convenio ?? 'Sin tipo registrado'}</td>
                  <td>{convenio.unidad_organizacional ?? 'Sin unidad registrada'}</td>
                  <td>{convenio.responsable ?? 'Sin dato registrado'}</td>
                  <td>
                    {formatearFecha(convenio.fecha_inicio)}
                    {' — '}
                    {formatearFecha(convenio.fecha_vencimiento)}
                  </td>
                  <td>
                    <span
                      className={`badge badge-${varianteEstado(convenio.estado)}`}
                      aria-label={`Estado: ${convenio.estado.replaceAll('_', ' ')}`}
                    >
                      {convenio.estado.replaceAll('_', ' ')}
                    </span>
                  </td>
                  <td>{textoActividades(convenio)}</td>
                  <td>
                    <Link className="btn btn-outline btn-small" to={`/convenios/${convenio.id}`}>
                      Ver convenio
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

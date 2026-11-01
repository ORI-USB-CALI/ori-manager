import { useState } from 'react'

import { useSesion } from '../auth/sesion'
import {
  urlDescargaEstadisticasConvenios,
  useReporteEstadisticasConvenios,
  type Conteo,
  type FiltrosEstadisticasConvenios,
} from './estadisticasConvenios'
import { ETIQUETA_TIPO, type EstadoConvenio, type TipoAliado } from './epica02'

const ESTADOS: EstadoConvenio[] = [
  'EN_TRAMITE',
  'VIGENTE',
  'POR_VENCER',
  'VENCIDO',
  'RENOVADO',
  'FINALIZADO',
  'CANCELADO',
]

const TIPOS_ALIADO: TipoAliado[] = ['UNIVERSIDAD', 'COLEGIO', 'EMPRESA', 'ENTIDAD_GUBERNAMENTAL']

function GraficoConteos({ titulo, conteos }: { titulo: string; conteos: Conteo[] }) {
  const maximo = Math.max(0, ...conteos.map((conteo) => conteo.cantidad))
  return (
    <section className="card estadisticas-agrupacion">
      <h3>{titulo}</h3>
      {conteos.length === 0 ? (
        <p>Sin datos para esta agrupación.</p>
      ) : (
        <>
          <figure className="estadisticas-grafico" aria-label={titulo}>
            <figcaption className="section-help">
              Número de convenios por categoría. Escala proporcional al mayor conteo de este gráfico.
            </figcaption>
            <ul className="estadisticas-barras">
              {conteos.map(({ etiqueta, cantidad }) => (
                <li key={etiqueta}>
                  <div className="estadisticas-barra-etiqueta">
                    <span>{etiqueta}</span><strong>{cantidad}</strong>
                  </div>
                  <div className="estadisticas-barra-fondo" aria-hidden="true">
                    <div
                      className="estadisticas-barra"
                      style={{ width: `${maximo > 0 ? cantidad / maximo * 100 : 0}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </figure>
          <details className="estadisticas-tabla">
            <summary>Ver tabla de datos</summary>
            <div className="table-container">
              <table className="table" aria-label={titulo}>
                <thead>
                  <tr>
                    <th scope="col">Categoría</th>
                    <th scope="col">Convenios</th>
                  </tr>
                </thead>
                <tbody>
                  {conteos.map((conteo) => (
                    <tr key={conteo.etiqueta}>
                      <td>{conteo.etiqueta}</td>
                      <td>{conteo.cantidad}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  )
}

export function ReporteEstadisticasConveniosPage() {
  const { puede } = useSesion()
  const autorizado = puede('convenios.ver_reportes')

  const [estado, setEstado] = useState<EstadoConvenio | ''>('')
  const [aliadoActivo, setAliadoActivo] = useState<'' | 'true' | 'false'>('')
  const [tipoAliado, setTipoAliado] = useState<TipoAliado | ''>('')
  const [pais, setPais] = useState('')

  const filtros: FiltrosEstadisticasConvenios = {
    estado: estado || undefined,
    aliado_activo: aliadoActivo === '' ? undefined : aliadoActivo === 'true',
    tipo_aliado: tipoAliado || undefined,
    pais: pais.trim() || undefined,
  }

  const reporte = useReporteEstadisticasConvenios(filtros, autorizado)

  if (!autorizado) return null

  const descargasDeshabilitadas = reporte.isPending || reporte.isFetching || reporte.isError
  const tieneDatos = reporte.data?.datos_suficientes && reporte.data.total_convenios > 0

  return (
    <>
      <section className="header-banner">
        <h1>Reporte estadístico de convenios</h1>
        <p>
          Estadísticas de convenios agrupadas por estado contractual, vigencia activa,
          estado y tipo del aliado, y país.
        </p>
      </section>

      <form
        className="table-filters-grid table-filters card"
        onSubmit={(evento) => evento.preventDefault()}
        aria-label="Filtros del reporte estadístico"
      >
        <label className="form-group">
          Estado del convenio
          <select
            className="form-control select"
            value={estado}
            onChange={(evento) => setEstado(evento.target.value as EstadoConvenio | '')}
          >
            <option value="">Todos</option>
            {ESTADOS.map((valor) => (
              <option key={valor} value={valor}>
                {valor.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </label>

        <label className="form-group">
          Estado del aliado
          <select
            className="form-control select"
            value={aliadoActivo}
            onChange={(evento) => setAliadoActivo(evento.target.value as '' | 'true' | 'false')}
          >
            <option value="">Todos</option>
            <option value="true">Activo</option>
            <option value="false">Inactivo</option>
          </select>
        </label>

        <label className="form-group">
          Tipo de aliado
          <select
            className="form-control select"
            value={tipoAliado}
            onChange={(evento) => setTipoAliado(evento.target.value as TipoAliado | '')}
          >
            <option value="">Todos</option>
            {TIPOS_ALIADO.map((valor) => (
              <option key={valor} value={valor}>
                {ETIQUETA_TIPO[valor]}
              </option>
            ))}
          </select>
        </label>

        <label className="form-group">
          País
          <input
            className="form-control"
            type="text"
            value={pais}
            placeholder="Nombre del país"
            onChange={(evento) => setPais(evento.target.value)}
          />
        </label>
      </form>

      <div className="page-toolbar">
        <div className="page-toolbar-group">
          {descargasDeshabilitadas ? (
            <>
              <button type="button" className="btn btn-outline" disabled>Descargar PDF</button>
              <button type="button" className="btn btn-outline" disabled>Descargar Excel</button>
            </>
          ) : (
            <>
              <a
                className="btn btn-outline"
                href={urlDescargaEstadisticasConvenios('pdf', filtros)}
              >
                Descargar PDF
              </a>
              <a
                className="btn btn-outline"
                href={urlDescargaEstadisticasConvenios('excel', filtros)}
              >
                Descargar Excel
              </a>
            </>
          )}
        </div>
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
        <p className="estado-pagina" role="status">Cargando estadísticas…</p>
      )}
      {reporte.isError && (
        <section className="alert-error" role="alert">
          <p>No se pudo consultar el reporte estadístico de convenios.</p>
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

      {reporte.isSuccess && !tieneDatos && (
        <div className="card estado-vacio">
          <p>No hay datos suficientes para generar el reporte estadístico.</p>
        </div>
      )}

      {reporte.isSuccess && reporte.data && tieneDatos && (
        <div className="estadisticas-grid">
          <GraficoConteos titulo="Por estado contractual" conteos={reporte.data.por_estado_contractual} />
          <GraficoConteos titulo="Por vigencia activa" conteos={reporte.data.por_vigencia_activa} />
          <GraficoConteos titulo="Por estado del aliado" conteos={reporte.data.por_estado_aliado} />
          <GraficoConteos titulo="Por tipo de aliado" conteos={reporte.data.por_tipo_aliado} />
          <GraficoConteos titulo="Por país" conteos={reporte.data.por_pais} />
        </div>
      )}
    </>
  )
}

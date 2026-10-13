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

function TablaConteos({ titulo, conteos }: { titulo: string; conteos: Conteo[] }) {
  return (
    <div className="card">
      <h3>{titulo}</h3>
      {conteos.length === 0 ? (
        <p>Sin datos para esta agrupación.</p>
      ) : (
        <table className="table">
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
      )}
    </div>
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
        className="table-filters-grid card"
        onSubmit={(evento) => evento.preventDefault()}
        aria-label="Filtros del reporte estadístico"
      >
        <label>
          Estado del convenio
          <select
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

        <label>
          Estado del aliado
          <select
            value={aliadoActivo}
            onChange={(evento) => setAliadoActivo(evento.target.value as '' | 'true' | 'false')}
          >
            <option value="">Todos</option>
            <option value="true">Activo</option>
            <option value="false">Inactivo</option>
          </select>
        </label>

        <label>
          Tipo de aliado
          <select
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

        <label>
          País
          <input
            type="text"
            value={pais}
            placeholder="Nombre del país"
            onChange={(evento) => setPais(evento.target.value)}
          />
        </label>
      </form>

      <div className="page-toolbar">
        <a
          className="btn btn-outline"
          href={urlDescargaEstadisticasConvenios('pdf', filtros)}
          aria-disabled={reporte.isPending || reporte.isError}
        >
          Descargar PDF
        </a>
        <a
          className="btn btn-outline"
          href={urlDescargaEstadisticasConvenios('excel', filtros)}
          aria-disabled={reporte.isPending || reporte.isError}
        >
          Descargar Excel
        </a>
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

      {reporte.data && !reporte.data.datos_suficientes && (
        <div className="card estado-vacio">
          <p>No hay datos suficientes para generar el reporte estadístico.</p>
        </div>
      )}

      {reporte.data && reporte.data.datos_suficientes && (
        <div className="estadisticas-grid">
          <TablaConteos titulo="Por estado contractual" conteos={reporte.data.por_estado_contractual} />
          <TablaConteos titulo="Por vigencia activa" conteos={reporte.data.por_vigencia_activa} />
          <TablaConteos titulo="Por estado del aliado" conteos={reporte.data.por_estado_aliado} />
          <TablaConteos titulo="Por tipo de aliado" conteos={reporte.data.por_tipo_aliado} />
          <TablaConteos titulo="Por país" conteos={reporte.data.por_pais} />
        </div>
      )}
    </>
  )
}

import { Link } from 'react-router-dom'

import { type ConvenioTablero, useTableroConvenios } from './epica02'

function identificador(convenio: ConvenioTablero) {
  return convenio.codigo ?? `Convenio #${convenio.id}`
}

function contraparte(convenio: ConvenioTablero) {
  return convenio.aliado?.nombre ?? convenio.aliado_propuesto ?? 'Contraparte por definir'
}

export function TableroConveniosPage() {
  const consulta = useTableroConvenios()

  return (
    <>
      <section className="header-banner">
        <h1>Tablero de convenios</h1>
        <p>Consulta el estado operativo de los convenios visibles para tu rol.</p>
      </section>

      {consulta.isPending && <p className="estado-pagina">Cargando tablero de convenios…</p>}
      {consulta.isError && <p className="alert-error" role="alert">No fue posible cargar el tablero: {consulta.error.message}</p>}

      {consulta.data && consulta.data.convenios.length === 0 && (
        <section className="card estado-vacio">
          <h2>No hay convenios visibles</h2>
          <p>No hay convenios en el tablero operativo.</p>
        </section>
      )}

      {consulta.data && consulta.data.convenios.length > 0 && (
        <div className="tablero-convenios" aria-label="Convenios agrupados por etapa">
          {consulta.data.etapas.map((etapa) => {
            const convenios = consulta.data.convenios.filter(
              (convenio) => convenio.etapa_actual?.id === etapa.id,
            )
            return (
              <section className="tablero-columna" key={etapa.id} aria-labelledby={`etapa-${etapa.id}`}>
                <header className="tablero-columna-header">
                  <div>
                    <h2 id={`etapa-${etapa.id}`}>{etapa.nombre}</h2>
                    <p>{etapa.area_responsable ?? 'Área por definir'}</p>
                  </div>
                  <span className="tablero-contador" aria-label={`${convenios.length} convenios`}>{convenios.length}</span>
                </header>
                <div className="tablero-tarjetas">
                  {convenios.length === 0 && <p className="tablero-etapa-vacia">Sin convenios en esta etapa</p>}
                  {convenios.map((convenio) => (
                    <article className="tablero-tarjeta" key={convenio.id}>
                      <div className="tablero-tarjeta-titulo">
                        <h3>{identificador(convenio)}</h3>
                        <span className="badge">{convenio.estado.replaceAll('_', ' ')}</span>
                      </div>
                      <dl>
                        <dt>Contraparte</dt>
                        <dd>{contraparte(convenio)}</dd>
                        <dt>Etapa</dt>
                        <dd>{convenio.etapa_actual?.nombre ?? 'Sin etapa asignada'}</dd>
                        <dt>Responsable</dt>
                        <dd>{convenio.responsable?.nombre_completo ?? etapa.area_responsable ?? 'Por definir'}</dd>
                      </dl>
                      {convenio.puede_ver_detalle && (
                        <Link className="btn btn-outline btn-small" to={`/convenios/${convenio.id}`}>Ver detalle</Link>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </>
  )
}

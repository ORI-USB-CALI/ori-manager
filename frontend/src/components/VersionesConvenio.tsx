import { Link } from 'react-router-dom'

import { ApiError } from '../app/api'
import { contextoVersion, useVersionesConvenio } from '../pages/epica02'

function fechaHora(valor: string) {
  return new Date(valor).toLocaleString()
}

/** HT-05. Versiones formales del convenio, consultables en cualquier etapa. */
export function VersionesConvenio({ convenioId }: { convenioId: number }) {
  const versiones = useVersionesConvenio(convenioId)

  if (versiones.isPending) return <p className="estado-pagina">Cargando versiones…</p>
  if (versiones.error instanceof ApiError && [403, 404].includes(versiones.error.status)) return null
  if (versiones.isError) {
    return <p className="alert-error" role="alert">No se pudieron consultar las versiones del convenio.</p>
  }

  const actual = Math.max(0, ...versiones.data.map((version) => version.numero))

  return (
    <section className="card" aria-labelledby="versiones-convenio-titulo">
      <h2 id="versiones-convenio-titulo">Versiones del convenio</h2>
      <p className="section-help">Solo incluye versiones formales; guardar avances no agrega versiones.</p>
      {versiones.data.length === 0 ? (
        <p>El convenio aún no tiene versiones registradas.</p>
      ) : (
        <div className="version-lista">
          {versiones.data.map((version) => (
            <article className={version.numero === actual ? 'version-actual' : undefined} key={version.numero}>
              <div className="version-cabecera">
                <strong>Versión {version.numero}</strong>
                {version.numero === actual && <span className="badge">Actual</span>}
              </div>
              <span><strong>Autor:</strong> {version.autor.nombre_completo}</span>
              <span><strong>Fecha:</strong> {fechaHora(version.creado_en)}</span>
              <span><strong>Etapa:</strong> {version.etapa.nombre}</span>
              <span><strong>Contexto:</strong> {contextoVersion(version.contexto)}</span>
              <Link
                className="version-enlace"
                to={`/convenios/${convenioId}/versiones/${version.numero}`}
                aria-label={`Ver contenido de la versión ${version.numero}`}
              >
                Ver contenido
              </Link>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

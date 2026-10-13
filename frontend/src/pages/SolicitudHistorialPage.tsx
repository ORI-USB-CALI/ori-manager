import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../app/api'
import { formatDateTime } from '../components/tableFormatters'
import { StatusBadge } from '../components/tablePresentation'
import {
  useHistorialSolicitud,
  type AlcanceHistorialSolicitud,
  type VersionSolicitudHistorial,
} from './solicitudes'

function Devolucion({ version }: { version: VersionSolicitudHistorial }) {
  const { devolucion } = version
  if (!devolucion) return null
  const corregida = devolucion.corregida_en_version
  return (
    <div className="timeline-observaciones">
      <span className="badge badge-warning">Devuelta</span>
      <p>{devolucion.observaciones}</p>
      <p className="texto-secundario">
        {devolucion.devuelta_por_nombre} · {formatDateTime(devolucion.devuelta_en)}
      </p>
      <p>
        {corregida ? (
          <>Corregida en la <a href={`#version-${corregida}`}>versión {corregida}</a></>
        ) : (
          'Pendiente de corrección por el Solicitante'
        )}
      </p>
    </div>
  )
}

export function SolicitudHistorialPage({ alcance }: { alcance: AlcanceHistorialSolicitud }) {
  const { solicitudId } = useParams()
  const id = Number(solicitudId)
  const valido = Number.isInteger(id) && id > 0
  const historial = useHistorialSolicitud(valido ? id : null, alcance)
  const volver = alcance === 'recibida'
    ? { to: `/ori/solicitudes/${id}`, texto: 'Volver a la solicitud' }
    : { to: '/solicitudes', texto: 'Volver a mis solicitudes' }

  if (!valido) return <p className="alert-error">Solicitud no encontrada</p>
  if (historial.isPending) return <p className="estado-pagina">Cargando historial…</p>
  if (historial.isError) {
    const noEncontrada = historial.error instanceof ApiError && historial.error.status === 404
    return (
      <section className="card estado-vacio">
        <h1>{noEncontrada ? 'Solicitud no encontrada' : 'No se pudo consultar el historial'}</h1>
        <Link className="btn btn-outline" to={volver.to}>{volver.texto}</Link>
      </section>
    )
  }

  const { consecutivo, estado, versiones } = historial.data
  const ultima = versiones.at(-1)?.numero

  return (
    <>
      <section className="header-banner">
        <h1>Historial de la solicitud</h1>
        <p>
          {consecutivo} · <StatusBadge value={estado} />
        </p>
      </section>

      <section className="card" aria-labelledby="radicaciones-titulo">
        <h2 id="radicaciones-titulo">Radicaciones</h2>
        <p className="section-help">
          Cada radicación queda guardada como una versión. Si la ORI la devolvió, se muestra la devolución y la versión que la corrigió.
        </p>
        {versiones.length === 0 ? (
          <p className="texto-secundario">La solicitud todavía no tiene radicaciones registradas.</p>
        ) : (
          <ol className="timeline">
            {versiones.map((version) => (
              <li className="timeline-item" id={`version-${version.numero}`} key={version.numero}>
                <p className="timeline-fecha">Radicada {formatDateTime(version.radicada_en)}</p>
                <p className="timeline-titulo">
                  Versión {version.numero}
                  {version.numero === ultima && !version.devolucion && (
                    <> <span className="badge badge-info">Versión vigente</span></>
                  )}
                </p>
                <Devolucion version={version} />
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="page-toolbar">
        <Link className="btn btn-outline" to={volver.to}>{volver.texto}</Link>
      </div>
    </>
  )
}

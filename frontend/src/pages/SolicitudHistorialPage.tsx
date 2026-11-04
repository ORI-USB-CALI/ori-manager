import { Link, useParams } from 'react-router-dom'

import { ApiError } from '../app/api'
import { StatusBadge } from '../components/tablePresentation'
import { VersionesSolicitud } from '../components/VersionesSolicitud'
import { useHistorialSolicitud, type AlcanceHistorialSolicitud } from './solicitudes'

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

  const { consecutivo, estado } = historial.data

  return (
    <>
      <section className="header-banner">
        <h1>Historial de la solicitud</h1>
        <p>
          {consecutivo} · <StatusBadge value={estado} />
        </p>
      </section>

      <VersionesSolicitud solicitudId={id} alcance={alcance} />

      <div className="page-toolbar">
        <Link className="btn btn-outline" to={volver.to}>{volver.texto}</Link>
      </div>
    </>
  )
}

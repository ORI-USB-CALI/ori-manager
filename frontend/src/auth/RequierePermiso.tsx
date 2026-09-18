import { Link, Navigate, Outlet } from 'react-router-dom'

import { type Permiso, useSesion } from './sesion'

export function RequierePermiso({ permiso }: { permiso: Permiso }) {
  const { sesion, cargando, puede } = useSesion()

  if (cargando) return <p className="estado-pagina">Validando acceso…</p>
  if (!sesion) return <Navigate to="/login" replace />
  if (!puede(permiso)) {
    return (
      <section className="card estado-vacio">
        <h1>Acceso denegado</h1>
        <p>No tiene permiso para consultar esta sección.</p>
        <Link to="/" className="btn btn-outline">
          Volver al inicio
        </Link>
      </section>
    )
  }

  return <Outlet />
}

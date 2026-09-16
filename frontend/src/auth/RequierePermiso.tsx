import { Link, Navigate, Outlet } from 'react-router-dom'

import { type Permiso, useSesion } from './sesion'

export function RequierePermiso({ permiso }: { permiso: Permiso }) {
  const { sesion, cargando, puede } = useSesion()

  if (cargando) return null
  if (!sesion) return <Navigate to="/login" replace />
  if (!puede(permiso)) {
    return (
      <section className="card">
        <h1>Acceso denegado</h1>
        <p>No tiene acceso a esta sección.</p>
        <Link to="/" className="btn btn-outline">
          Volver al inicio
        </Link>
      </section>
    )
  }

  return <Outlet />
}

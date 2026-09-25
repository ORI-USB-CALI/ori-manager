import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useSesion } from '../auth/sesion'
import { apiFetch } from './api'

export function AppLayout() {
  const { sesion, cargando, error, puede } = useSesion()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const logout = useMutation({
    mutationFn: () => apiFetch('/auth/logout', { method: 'POST' }),
    onSuccess: () => {
      queryClient.clear()
      navigate('/login', { replace: true })
    },
  })

  if (cargando) return <p className="estado-pagina">Cargando sesión…</p>
  if (error) {
    return (
      <main className="login-page">
        <section className="card estado-vacio">
          <h1>No se pudo validar la sesión</h1>
          <p>{error.message}</p>
        </section>
      </main>
    )
  }
  if (!sesion) return <Navigate to="/login" replace />

  return (
    <div className="app-shell">
      <header className="navbar">
        <Link to="/" className="navbar-brand">
          ORI<span className="navbar-brand-extra"> · Sistema de Gestión</span>
        </Link>

        <nav className="navbar-links" aria-label="Navegación principal">
          <NavLink to="/" end>
            Inicio
          </NavLink>
          {puede('aliados.ver') && <NavLink to="/aliados">Aliados</NavLink>}
          {puede('solicitudes.ver_recibidas') && <NavLink to="/ori/solicitudes">Solicitudes recibidas</NavLink>}
          {puede('solicitudes.ver_propias') && <NavLink to="/solicitudes">Mis solicitudes</NavLink>}
          {puede('usuarios.ver') && <NavLink to="/admin/usuarios">Usuarios</NavLink>}
        </nav>

        <div className="user-profile">
          <div className="user-data">
            <span className="user-email">{sesion.correo}</span>
            <span className="badge badge-rol">{sesion.rol.nombre}</span>
          </div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            {logout.isPending ? 'Saliendo…' : 'Cerrar sesión'}
          </button>
        </div>
      </header>

      {logout.isError && (
        <p className="alert-error alert-global" role="alert">
          No se pudo cerrar la sesión: {logout.error.message}
        </p>
      )}

      <main className="page">
        <Outlet />
      </main>

      <footer className="footer-internal">
        <span>© Universidad de San Buenaventura Cali — Sistema de Gestión ORI</span>
        <span>v0.1.0</span>
      </footer>
    </div>
  )
}

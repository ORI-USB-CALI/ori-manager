import { useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { ETIQUETAS_ROL, useSesion } from '../auth/sesion'
import { apiFetch } from './api'

export function AppLayout() {
  const { sesion, puede } = useSesion()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  async function cerrarSesion() {
    await apiFetch('/auth/logout', { method: 'POST' })
    // Limpia todo el caché para no mostrar datos del usuario anterior.
    queryClient.clear()
    navigate('/login')
  }

  return (
    <>
      <header className="navbar">
        <Link to="/" className="navbar-brand">
          ORI<span className="navbar-brand-extra"> · Sistema de Gestión</span>
        </Link>

        <nav className="navbar-links">
          <NavLink to="/" end>
            Inicio
          </NavLink>
          {puede('usuarios.gestionar') && <NavLink to="/admin/usuarios">Usuarios</NavLink>}
        </nav>

        <div className="user-profile">
          {sesion ? (
            <>
              <span className="user-email">{sesion.email}</span>
              <span className="badge badge-rol">{ETIQUETAS_ROL[sesion.rol]}</span>
              <button type="button" className="btn btn-outline" onClick={cerrarSesion}>
                Cerrar sesión
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary">
              Iniciar sesión
            </Link>
          )}
        </div>
      </header>

      <main className="page">
        <Outlet />
      </main>

      <footer className="footer-internal">
        <span>© Universidad de San Buenaventura Cali — Sistema de Gestión ORI</span>
        <span>v0.1.0</span>
      </footer>
    </>
  )
}

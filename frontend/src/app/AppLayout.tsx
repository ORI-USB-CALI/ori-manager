import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { guardarRol, obtenerRol } from '../api/http'
import type { RolUsuario } from '../features/aliados/types'

const ROLES: { valor: RolUsuario; etiqueta: string }[] = [
  { valor: 'administrador_ori', etiqueta: 'Administrador ORI' },
  { valor: 'gestor_ori', etiqueta: 'Gestor ORI' },
  { valor: 'revisor_ori', etiqueta: 'Revisor ORI' },
  { valor: 'solicitante_interno', etiqueta: 'Solicitante interno' },
]

export function AppLayout() {
  const queryClient = useQueryClient()
  const [rol, setRol] = useState<RolUsuario>(obtenerRol)

  // Selector temporal: reemplazar por la sesión real cuando exista HU-01.
  function cambiarRol(nuevo: RolUsuario) {
    guardarRol(nuevo)
    setRol(nuevo)
    queryClient.invalidateQueries()
  }

  return (
    <>
      <header className="navbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <Link to="/" className="navbar-brand">
            ORI <span>Manager</span>
          </Link>
          <nav style={{ display: 'flex', gap: '20px' }}>
            <NavLink
              to="/aliados"
              style={({ isActive }) => ({
                fontSize: '0.875rem',
                fontWeight: 600,
                textDecoration: 'none',
                color: isActive ? 'var(--color-naranja)' : 'var(--text-secondary)',
              })}
            >
              Aliados
            </NavLink>
          </nav>
        </div>
        <div className="user-profile">
          <label htmlFor="rol" className="caption">
            Rol
          </label>
          <select
            id="rol"
            className="form-control"
            style={{ height: '34px' }}
            value={rol}
            onChange={(e) => cambiarRol(e.target.value as RolUsuario)}
          >
            {ROLES.map((r) => (
              <option key={r.valor} value={r.valor}>
                {r.etiqueta}
              </option>
            ))}
          </select>
        </div>
      </header>

      <main className="main-content">
        <Outlet context={{ rol }} />
      </main>

      <footer className="footer-internal">
        <span>© Universidad de San Buenaventura Cali — Sistema de Gestión ORI</span>
        <div>
          <span>v1.0.0</span>
        </div>
      </footer>
    </>
  )
}

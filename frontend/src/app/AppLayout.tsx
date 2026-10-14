import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useSesion } from '../auth/sesion'
import { BandejaNotificaciones } from '../components/BandejaNotificaciones'
import { CentroNotificaciones } from '../components/CentroNotificaciones'
import { useCentroNotificaciones } from '../pages/centroNotificaciones'
import { useNotificacionesTiempoReal } from '../pages/notificaciones'
import { apiFetch } from './api'

export function AppLayout() {
  const { sesion, cargando, error, puede } = useSesion()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const centro = useCentroNotificaciones()
  useNotificacionesTiempoReal(Boolean(sesion))
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
          {puede('convenios.ver') && <NavLink to="/convenios">Consulta de convenios</NavLink>}
          {puede('convenios.crear') && <NavLink to="/convenios/nuevo">Crear convenio manual</NavLink>}
          {puede('convenios.ver') && <NavLink to="/convenios/tablero">Tablero de convenios</NavLink>}
          {puede('convenios.gestionar_renovaciones') && <NavLink to="/renovaciones">Renovaciones</NavLink>}
          {puede('convenios.ver_reportes') && <NavLink to="/reportes/convenios-activos">Reportes</NavLink>}
          {puede('convenios.ver_reportes') && (
            <NavLink to="/reportes/estadisticas-convenios">Estadísticas</NavLink>
          )}
          {puede('convenios.revisar') && <NavLink to="/revisiones-juridicas">Revisiones jurídicas</NavLink>}
          {puede('solicitudes.ver_propias') && <NavLink to="/solicitudes">Mis solicitudes</NavLink>}
          {puede('usuarios.ver') && <NavLink to="/admin/usuarios">Usuarios</NavLink>}
          {puede('auditoria.ver') && <NavLink to="/admin/bitacora">Bitácora</NavLink>}
        </nav>

        <div className="user-profile">
          <BandejaNotificaciones
            nombre="Centro de notificaciones"
            contador={centro.contador}
            onAbrir={centro.refrescar}
          >
            <CentroNotificaciones
              fuentes={centro.fuentes}
              actualizando={centro.actualizando}
              onActualizar={centro.refrescar}
            />
          </BandejaNotificaciones>
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

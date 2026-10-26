import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, Outlet, useNavigate } from 'react-router-dom'

import { useSesion } from '../auth/sesion'
import { BandejaNotificaciones } from '../components/BandejaNotificaciones'
import { CentroNotificaciones } from '../components/CentroNotificaciones'
import { HeaderNav, type EnlaceNav } from '../components/HeaderNav'
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

  const enlaces: EnlaceNav[] = [
    { to: '/', label: 'Inicio', end: true },
    puede('aliados.ver') && { to: '/aliados', label: 'Aliados' },
    puede('solicitudes.ver_recibidas') && { to: '/ori/solicitudes', label: 'Solicitudes recibidas' },
    puede('convenios.ver') && { to: '/convenios', label: 'Consulta de convenios' },
    puede('convenios.crear') && { to: '/convenios/nuevo', label: 'Crear convenio manual' },
    puede('convenios.ver') && { to: '/convenios/tablero', label: 'Tablero de convenios' },
    puede('convenios.gestionar_renovaciones') && { to: '/renovaciones', label: 'Renovaciones' },
    puede('convenios.ver_reportes') && { to: '/reportes/convenios-activos', label: 'Reportes' },
    puede('convenios.ver_reportes') && { to: '/reportes/estadisticas-convenios', label: 'Estadísticas' },
    puede('convenios.revisar') && { to: '/revisiones-juridicas', label: 'Revisiones jurídicas' },
    puede('solicitudes.ver_propias') && { to: '/solicitudes', label: 'Mis solicitudes' },
    puede('usuarios.ver') && { to: '/admin/usuarios', label: 'Usuarios' },
    puede('auditoria.ver') && { to: '/admin/bitacora', label: 'Bitácora' },
  ].filter((enlace): enlace is EnlaceNav => Boolean(enlace))

  return (
    <div className="app-shell">
      <header className="navbar">
        <Link to="/" className="navbar-brand">
          ORI<span className="navbar-brand-extra"> · Sistema de Gestión</span>
        </Link>

        <HeaderNav enlaces={enlaces} />

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

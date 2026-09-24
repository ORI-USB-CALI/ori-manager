import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import {
  ETIQUETAS_ROL,
  type CodigoRol,
  type TipoUsuario,
  useSesion,
} from '../auth/sesion'
import { Select } from '../components/Select'
import { UsuarioModal } from './UsuarioModal'
import { CLAVE_USUARIOS, type Usuario, etiquetaTipo } from './usuarios'

type EstadoModal = null | 'nuevo' | Usuario
type FiltroEstado = '' | 'activo' | 'inactivo'

const OPCIONES_TIPO = [
  { value: '', label: 'Todos' },
  { value: 'INTERNO', label: 'Interno' },
  { value: 'EXTERNO', label: 'Externo' },
]

const OPCIONES_ROL = [
  { value: '', label: 'Todos' },
  ...Object.entries(ETIQUETAS_ROL).map(([value, label]) => ({ value, label })),
]

const OPCIONES_ESTADO = [
  { value: '', label: 'Todos' },
  { value: 'activo', label: 'Activo' },
  { value: 'inactivo', label: 'Inactivo' },
]

export function UsuariosRolesPage() {
  const { sesion, puede } = useSesion()
  const [modal, setModal] = useState<EstadoModal>(null)
  const [busqueda, setBusqueda] = useState('')
  const [tipo, setTipo] = useState<TipoUsuario | ''>('')
  const [rol, setRol] = useState<CodigoRol | ''>('')
  const [estado, setEstado] = useState<FiltroEstado>('')
  const queryClient = useQueryClient()
  const usuarios = useQuery({
    queryKey: CLAVE_USUARIOS,
    queryFn: () => apiFetch<Usuario[]>('/usuarios'),
    retry: false,
  })
  const puedeGestionar =
    puede('usuarios.editar') ||
    puede('usuarios.cambiar_rol') ||
    puede('usuarios.cambiar_estado')
  const hayFiltros = Boolean(busqueda.trim() || tipo || rol || estado)
  const usuariosFiltrados = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase('es')
    return (usuarios.data ?? []).filter((usuario) => {
      const coincideBusqueda =
        !termino ||
        `${usuario.nombre_completo} ${usuario.correo}`
          .toLocaleLowerCase('es')
          .includes(termino)
      const coincideTipo = !tipo || usuario.tipo_usuario === tipo
      const coincideRol = !rol || usuario.rol.codigo === rol
      const coincideEstado =
        !estado || usuario.activo === (estado === 'activo')
      return coincideBusqueda && coincideTipo && coincideRol && coincideEstado
    })
  }, [busqueda, estado, rol, tipo, usuarios.data])

  async function usuarioGuardado() {
    await queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS })
  }

  function limpiarFiltros() {
    setBusqueda('')
    setTipo('')
    setRol('')
    setEstado('')
  }

  return (
    <>
      <section className="header-banner">
        <h1>Administración de usuarios</h1>
        <p>Consulte usuarios y gestione sus datos, roles y estado de acceso.</p>
      </section>

      <div className="page-toolbar">
        <div>
          <h2>Usuarios</h2>
          <p className="texto-secundario">Identidades autenticadas registradas en ORI Manager.</p>
        </div>
        {puede('usuarios.crear') && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setModal('nuevo')}
          >
            Nuevo usuario
          </button>
        )}
      </div>

      {usuarios.isError && (
        <p className="alert-error" role="alert">
          {usuarios.error instanceof ApiError
            ? usuarios.error.message
            : 'No se pudo cargar el listado de usuarios.'}
        </p>
      )}

      {usuarios.isPending && <p className="estado-pagina">Cargando usuarios…</p>}

      {usuarios.data?.length === 0 && (
        <section className="card estado-vacio">
          <h3>No hay usuarios</h3>
          <p>El listado está vacío.</p>
        </section>
      )}

      {usuarios.data && usuarios.data.length > 0 && (
        <>
          <section className="card usuarios-filtros" aria-label="Filtros de usuarios">
            <div className="usuarios-filtros-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="usuarios-busqueda">
                  Buscar
                </label>
                <input
                  id="usuarios-busqueda"
                  type="search"
                  className="form-control"
                  value={busqueda}
                  placeholder="Nombre o correo"
                  onChange={(evento) => setBusqueda(evento.target.value)}
                />
              </div>
              <Select
                id="usuarios-tipo"
                label="Tipo"
                value={tipo}
                opciones={OPCIONES_TIPO}
                onChange={(evento) => setTipo(evento.target.value as TipoUsuario | '')}
              />
              <Select
                id="usuarios-rol"
                label="Rol"
                value={rol}
                opciones={OPCIONES_ROL}
                onChange={(evento) => setRol(evento.target.value as CodigoRol | '')}
              />
              <Select
                id="usuarios-estado"
                label="Estado"
                value={estado}
                opciones={OPCIONES_ESTADO}
                onChange={(evento) => setEstado(evento.target.value as FiltroEstado)}
              />
            </div>
            {hayFiltros && (
              <button type="button" className="btn btn-outline btn-small" onClick={limpiarFiltros}>
                Limpiar filtros
              </button>
            )}
          </section>

          {usuariosFiltrados.length === 0 ? (
            <section className="card estado-vacio">
              <h3>Sin resultados</h3>
              <p>No hay usuarios que coincidan con los filtros seleccionados.</p>
            </section>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Correo</th>
                    <th>Tipo</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {usuariosFiltrados.map((usuario) => (
                    <tr key={usuario.id}>
                      <td>
                        <strong>{usuario.nombre_completo}</strong>
                        {usuario.id === sesion?.id && (
                          <small className="tabla-ayuda">Usted</small>
                        )}
                      </td>
                      <td>{usuario.correo}</td>
                      <td>{etiquetaTipo(usuario.tipo_usuario)}</td>
                      <td>
                        <span className="badge badge-rol">{usuario.rol.nombre}</span>
                      </td>
                      <td>
                        <span
                          className={`badge ${usuario.activo ? 'badge-activo' : 'badge-inactivo'}`}
                        >
                          {usuario.activo ? 'Activo' : 'Inactivo'}
                        </span>
                      </td>
                      <td>
                        {puedeGestionar ? (
                          <button
                            type="button"
                            className="btn btn-outline btn-small"
                            onClick={() => setModal(usuario)}
                          >
                            Gestionar
                          </button>
                        ) : (
                          <span className="texto-secundario">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {modal && (
        <UsuarioModal
          key={modal === 'nuevo' ? 'nuevo' : modal.id}
          usuario={modal === 'nuevo' ? undefined : modal}
          onGuardado={usuarioGuardado}
          onCerrar={() => setModal(null)}
        />
      )}
    </>
  )
}

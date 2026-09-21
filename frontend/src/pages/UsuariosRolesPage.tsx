import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError, apiFetch } from '../app/api'
import { useSesion } from '../auth/sesion'
import { UsuarioModal } from './UsuarioModal'
import { CLAVE_USUARIOS, type Usuario, etiquetaTipo } from './usuarios'

type EstadoModal = null | 'nuevo' | Usuario

export function UsuariosRolesPage() {
  const { sesion, puede } = useSesion()
  const [modal, setModal] = useState<EstadoModal>(null)
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

  async function usuarioGuardado() {
    await queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS })
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
              {usuarios.data.map((usuario) => (
                <tr key={usuario.id}>
                  <td>
                    <strong>{usuario.nombre_completo}</strong>
                    {usuario.id === sesion?.id && <small className="tabla-ayuda">Usted</small>}
                  </td>
                  <td>{usuario.correo}</td>
                  <td>{etiquetaTipo(usuario.tipo_usuario)}</td>
                  <td>
                    <span className="badge badge-rol">{usuario.rol.nombre}</span>
                  </td>
                  <td>
                    <span className={`badge ${usuario.activo ? 'badge-activo' : 'badge-inactivo'}`}>
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

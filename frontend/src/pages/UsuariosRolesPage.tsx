import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { apiFetch } from '../app/api'
import { ETIQUETAS_ROL, useSesion } from '../auth/sesion'
import { type Usuario, UsuarioModal } from './UsuarioModal'

const CLAVE_USUARIOS = ['usuarios'] as const

// null = cerrado, 'nuevo' = crear, Usuario = editar.
type EstadoModal = null | 'nuevo' | Usuario

export function UsuariosRolesPage() {
  const { sesion } = useSesion()
  const [modal, setModal] = useState<EstadoModal>(null)
  const queryClient = useQueryClient()
  const usuarios = useQuery({
    queryKey: CLAVE_USUARIOS,
    queryFn: () => apiFetch<Usuario[]>('/usuarios'),
  })

  return (
    <>
      <section className="header-banner">
        <h1>Usuarios</h1>
        <p>Cree usuarios y gestione su correo, contraseña, rol y estado.</p>
      </section>

      <div className="page-toolbar">
        <h2>Listado</h2>
        <button type="button" className="btn btn-primary" onClick={() => setModal('nuevo')}>
          Nuevo usuario
        </button>
      </div>

      {usuarios.isError && (
        <p className="alert-error" role="alert">
          No se pudo cargar el listado: {usuarios.error.message}
        </p>
      )}

      {usuarios.isPending && <p className="caption">Cargando usuarios…</p>}

      {usuarios.data && (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.data.map((usuario) => (
                <tr key={usuario.id}>
                  <td>
                    {usuario.email}
                    {usuario.id === sesion?.id && <small> (usted)</small>}
                  </td>
                  <td>
                    <span className="badge badge-rol">{ETIQUETAS_ROL[usuario.rol]}</span>
                  </td>
                  <td>
                    <span className={`badge ${usuario.is_active ? 'badge-activo' : 'badge-inactivo'}`}>
                      {usuario.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-outline"
                      aria-label={`Editar ${usuario.email}`}
                      onClick={() => setModal(usuario)}
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <UsuarioModal
          // key: al abrir otro usuario el formulario se reinicia con sus datos.
          key={modal === 'nuevo' ? 'nuevo' : modal.id}
          usuario={modal === 'nuevo' ? undefined : modal}
          esPropio={modal !== 'nuevo' && modal.id === sesion?.id}
          onGuardado={() => queryClient.invalidateQueries({ queryKey: CLAVE_USUARIOS })}
          onCerrar={() => setModal(null)}
        />
      )}
    </>
  )
}

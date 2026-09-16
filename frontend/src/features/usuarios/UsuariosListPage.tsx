import { Link } from 'react-router-dom'

import { useDesactivarUsuario, useUsuarios } from './hooks'
import './usuarios.css'

export function UsuariosListPage() {
  const { data: usuarios, isPending, isError, error } = useUsuarios()
  const desactivarUsuario = useDesactivarUsuario()

  function manejarDesactivar(id: number, nombre: string) {
    const confirmado = window.confirm(`¿Desactivar a ${nombre}? Podrá reactivarse más adelante.`)
    if (!confirmado) return
    desactivarUsuario.mutate(id)
  }

  return (
    <main className="usuarios-page">
      <div className="usuarios-page__encabezado">
        <div>
          <h1>Usuarios internos</h1>
          <p>Administradores, gestores y revisores ORI con acceso al sistema.</p>
        </div>
        <Link to="/usuarios/nuevo" className="btn btn-primary">
          Nuevo usuario
        </Link>
      </div>

      <div className="usuarios-tabla-contenedor">
        {isPending && <p className="usuarios-estado-mensaje">Cargando usuarios…</p>}

        {isError && (
          <p className="usuarios-estado-mensaje">
            No se pudo cargar el listado: {error instanceof Error ? error.message : 'error desconocido'}
          </p>
        )}

        {usuarios && usuarios.length === 0 && (
          <p className="usuarios-estado-mensaje">Todavía no hay usuarios internos registrados.</p>
        )}

        {usuarios && usuarios.length > 0 && (
          <table className="usuarios-tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((usuario) => (
                <tr key={usuario.id}>
                  <td>{usuario.nombre_completo}</td>
                  <td>{usuario.correo}</td>
                  <td>
                    <span className="badge badge-rol">{usuario.rol.nombre}</span>
                  </td>
                  <td>
                    <span className={`badge ${usuario.activo ? 'badge-activo' : 'badge-inactivo'}`}>
                      {usuario.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="usuarios-tabla__acciones">
                    <Link to={`/usuarios/${usuario.id}/editar`} className="btn btn-outline">
                      Editar
                    </Link>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      disabled={!usuario.activo || desactivarUsuario.isPending}
                      onClick={() => manejarDesactivar(usuario.id, usuario.nombre_completo)}
                        >
                      {usuario.activo ? 'Desactivar': 'Inactivo'}
                   
                      Desactivar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  )
}

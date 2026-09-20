import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import { ETIQUETA_TIPO, type Aliado, type TipoAliado } from './epica02'

export function AliadosPage() {
  const [buscar, setBuscar] = useState('')
  const [consulta, setConsulta] = useState('')
  const aliados = useQuery({
    queryKey: ['aliados', consulta],
    queryFn: () =>
      apiFetch<{ items: Aliado[]; total: number }>(`/aliados?limite=100${consulta}`),
    retry: false,
  })

  function filtrar(evento: FormEvent) {
    evento.preventDefault()
    setConsulta(buscar.trim() ? `&buscar=${encodeURIComponent(buscar.trim())}` : '')
  }

  return (
    <>
      <section className="header-banner">
        <h1>Gestión de aliados</h1>
        <p>Consulte las entidades reconocidas al formalizar convenios.</p>
      </section>
      <form className="card page-toolbar" onSubmit={filtrar}>
        <div className="form-group">
          <label className="form-label" htmlFor="buscar-aliado">Nombre o NIT/documento</label>
          <input id="buscar-aliado" className="form-control" value={buscar} onChange={(e) => setBuscar(e.target.value)} />
        </div>
        <button className="btn btn-primary" type="submit">Buscar</button>
      </form>
      {aliados.isPending && <p className="estado-pagina">Cargando aliados…</p>}
      {aliados.isError && (
        <p className="alert-error" role="alert">
          {aliados.error instanceof ApiError ? aliados.error.message : 'No se pudo cargar el listado.'}
        </p>
      )}
      {aliados.data?.items.length === 0 && <section className="card estado-vacio"><h2>No hay aliados</h2></section>}
      {aliados.data && aliados.data.items.length > 0 && (
        <div className="table-container">
          <table className="table">
            <thead><tr><th>Nombre</th><th>NIT / documento</th><th>Tipo</th><th>Estado</th><th>Acciones</th></tr></thead>
            <tbody>{aliados.data.items.map((aliado) => (
              <tr key={aliado.id}>
                <td><strong>{aliado.nombre}</strong></td>
                <td>{aliado.identificacion}</td>
                <td>{ETIQUETA_TIPO[aliado.tipo as TipoAliado]}</td>
                <td><span className={`badge ${aliado.activo ? 'badge-activo' : 'badge-inactivo'}`}>{aliado.activo ? 'ACTIVO' : 'INACTIVO'}</span></td>
                <td><Link className="btn btn-outline btn-small" to={`/aliados/${aliado.id}`}>Ver perfil</Link></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </>
  )
}

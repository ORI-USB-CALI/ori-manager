import { useState, type FormEvent } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { puedeGestionar } from '../api/http'
import { useAliados } from '../features/aliados/hooks'
import {
  TIPO_ALIADO_ETIQUETA,
  type EstadoAliado,
  type FiltrosAliado,
  type RolUsuario,
  type TipoAliado,
} from '../features/aliados/types'

const POR_PAGINA = 10

export function AliadosPage() {
  const { rol } = useOutletContext<{ rol: RolUsuario }>()
  const [searchParams] = useSearchParams()

  const [buscar, setBuscar] = useState(searchParams.get('buscar') ?? '')
  const [tipo, setTipo] = useState<TipoAliado | ''>('')
  const [estado, setEstado] = useState<EstadoAliado | ''>('')
  const [filtros, setFiltros] = useState<FiltrosAliado>({
    buscar: searchParams.get('buscar') ?? undefined,
    limite: POR_PAGINA,
    desplazamiento: 0,
  })

  const { data, isPending, isError, error, refetch } = useAliados(filtros)

  function aplicarFiltros(e: FormEvent) {
    e.preventDefault()
    setFiltros({
      buscar: buscar.trim() || undefined,
      tipo: tipo || undefined,
      estado: estado || undefined,
      limite: POR_PAGINA,
      desplazamiento: 0,
    })
  }

  function limpiar() {
    setBuscar('')
    setTipo('')
    setEstado('')
    setFiltros({ limite: POR_PAGINA, desplazamiento: 0 })
  }

  function cambiarPagina(delta: number) {
    setFiltros((f) => ({ ...f, desplazamiento: Math.max(0, f.desplazamiento + delta * POR_PAGINA) }))
  }

  const total = data?.total ?? 0
  const desde = total === 0 ? 0 : filtros.desplazamiento + 1
  const hasta = Math.min(filtros.desplazamiento + POR_PAGINA, total)

  return (
    <>
      <div className="header-banner">
        <div>
          <h1>Gestión de aliados</h1>
          <p>Una sola identidad institucional por entidad. Busca antes de crear para no duplicar.</p>
        </div>
        {puedeGestionar(rol) && (
          <Link to="/aliados/nuevo" className="btn btn-primary" style={{ marginTop: '12px' }}>
            Nuevo aliado
          </Link>
        )}
      </div>

      <form className="card" onSubmit={aplicarFiltros}>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ flex: '1 1 260px', marginBottom: 0 }}>
            <label htmlFor="buscar" className="form-label">
              Buscar por identificación o nombre
            </label>
            <input
              id="buscar"
              type="search"
              className="form-control"
              value={buscar}
              onChange={(e) => setBuscar(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ width: '220px', marginBottom: 0 }}>
            <label htmlFor="tipo" className="form-label">
              Tipo
            </label>
            <select
              id="tipo"
              className="form-control"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TipoAliado | '')}
            >
              <option value="">Todos los tipos</option>
              {Object.entries(TIPO_ALIADO_ETIQUETA).map(([valor, etiqueta]) => (
                <option key={valor} value={valor}>
                  {etiqueta}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ width: '160px', marginBottom: 0 }}>
            <label htmlFor="estado" className="form-label">
              Estado
            </label>
            <select
              id="estado"
              className="form-control"
              value={estado}
              onChange={(e) => setEstado(e.target.value as EstadoAliado | '')}
            >
              <option value="">Todos</option>
              <option value="activo">Activo</option>
              <option value="inactivo">Inactivo</option>
            </select>
          </div>
          <button type="submit" className="btn btn-primary">
            Buscar
          </button>
          <button type="button" className="btn btn-outline" onClick={limpiar}>
            Limpiar
          </button>
        </div>
      </form>

      {isPending && (
        <div className="state-container">
          <h3 className="state-title">Cargando aliados...</h3>
        </div>
      )}

      {isError && (
        <div className="state-container alert-forbidden">
          <h3 className="state-title">No se pudo cargar el listado</h3>
          <p className="state-description">{error.message}</p>
          <button type="button" className="btn btn-secondary" onClick={() => refetch()}>
            Reintentar
          </button>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="state-container">
          <h3 className="state-title">Ningún aliado coincide con la búsqueda</h3>
          <p className="state-description">
            Revisa la identificación o registra la entidad como nuevo aliado.
          </p>
          {puedeGestionar(rol) && (
            <Link to="/aliados/nuevo" className="btn btn-primary">
              Crear aliado
            </Link>
          )}
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Identificación</th>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Ciudad</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <strong>{a.identificacion}</strong>
                    </td>
                    <td>
                      <Link to={`/aliados/${a.id}`}>{a.nombre}</Link>
                    </td>
                    <td>
                      {TIPO_ALIADO_ETIQUETA[a.tipo]}
                      {a.sector_economico ? ` · ${a.sector_economico}` : ''}
                    </td>
                    <td>{a.ciudad ?? '—'}</td>
                    <td>
                      <span className={`badge badge-${a.estado}`}>{a.estado}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '12px 16px',
            }}
          >
            <small>
              Mostrando {desde}–{hasta} de {total} aliados
            </small>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-outline"
                disabled={filtros.desplazamiento === 0}
                onClick={() => cambiarPagina(-1)}
              >
                Anterior
              </button>
              <button
                type="button"
                className="btn btn-outline"
                disabled={hasta >= total}
                onClick={() => cambiarPagina(1)}
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

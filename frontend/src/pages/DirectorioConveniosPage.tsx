// HU-09: directorio público de convenios vigentes. No requiere sesión.
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'

export interface ConvenioPublico {
  codigo: string
  aliado: string
  tipo_convenio: string | null
  objeto: string | null
  fecha_inicio: string
  fecha_vencimiento: string
  estado: 'VIGENTE'
}

interface DirectorioPublico {
  items: ConvenioPublico[]
  total: number
}

const POR_PAGINA = 20

function formatearFecha(fecha: string | null): string {
  if (!fecha) return 'Sin fecha registrada'
  return new Date(`${fecha}T00:00:00Z`).toLocaleDateString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  })
}

export function DirectorioConveniosPage() {
  const [pagina, setPagina] = useState(0)
  const directorio = useQuery({
    queryKey: ['directorio-publico', pagina],
    queryFn: () => apiFetch<DirectorioPublico>(
      `/public/directorio-convenios?limite=${POR_PAGINA}&desplazamiento=${pagina * POR_PAGINA}`,
    ),
  })
  const total = directorio.data?.total ?? 0
  const paginas = Math.ceil(total / POR_PAGINA)

  let contenido
  if (directorio.isPending) {
    contenido = <p className="estado-pagina">Cargando convenios vigentes…</p>
  } else if (directorio.isError) {
    contenido = <p className="estado-pagina" role="alert">No se pudo cargar el directorio. Intenta nuevamente más tarde.</p>
  } else if (directorio.data.items.length === 0) {
    contenido = <section className="card estado-vacio"><p>No hay convenios vigentes disponibles en este momento.</p></section>
  } else {
    contenido = (
      <>
        <div className="table-container" role="region" aria-label="Convenios vigentes" tabIndex={0}>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Convenio</th>
                <th scope="col">Institución o aliado</th>
                <th scope="col">Tipo</th>
                <th scope="col">Objeto</th>
                <th scope="col">Inicio</th>
                <th scope="col">Finalización</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {directorio.data.items.map((convenio) => (
                <tr key={convenio.codigo}>
                  <td>{convenio.codigo}</td>
                  <td>{convenio.aliado}</td>
                  <td>{convenio.tipo_convenio ?? '—'}</td>
                  <td>{convenio.objeto ?? '—'}</td>
                  <td>{formatearFecha(convenio.fecha_inicio)}</td>
                  <td>{formatearFecha(convenio.fecha_vencimiento)}</td>
                  <td><span className="badge badge-success">Vigente</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {paginas > 1 && (
          <nav className="table-filters-actions" aria-label="Paginación del directorio">
            <button type="button" className="btn btn-outline btn-small" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>Anterior</button>
            <span>Página {pagina + 1} de {paginas}</span>
            <button type="button" className="btn btn-outline btn-small" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
          </nav>
        )}
      </>
    )
  }

  return (
    <div className="revision-publica-shell">
      <header className="revision-publica-header">
        <div>
          <strong>ORI</strong>
          <span>Oficina de Relaciones Interinstitucionales</span>
        </div>
        <Link to="/login">Iniciar sesión</Link>
      </header>
      <main className="revision-publica-main">
        <section className="revision-publica-presentacion">
          <h1>Directorio de convenios vigentes</h1>
          <p>Consulta los convenios que la universidad tiene vigentes con otras instituciones.</p>
        </section>
        {contenido}
      </main>
      <footer className="revision-publica-footer">Universidad de San Buenaventura · Gestión de convenios</footer>
    </div>
  )
}

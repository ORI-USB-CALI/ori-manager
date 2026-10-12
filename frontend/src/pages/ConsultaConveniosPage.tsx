import { type FormEvent, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '../app/api'
import {
  DataTable,
  ResultsCount,
  TableEmptyState,
  type DataTableColumn,
} from '../components/DataTable'
import { TableFilters } from '../components/TableFilters'
import { StatusBadge } from '../components/tablePresentation'
import { type ConvenioConsulta, useConsultaConvenios } from './consultaConvenios'
import { ETIQUETA_TIPO } from './epica02'

const LIMITE = 20

function contraparte(convenio: ConvenioConsulta) {
  const { contraparte: datos } = convenio
  if (!datos.nombre) return 'Contraparte por definir'
  const tipo = datos.tipo ? ETIQUETA_TIPO[datos.tipo] : null
  return tipo ? `${datos.nombre} (${tipo})` : datos.nombre
}

export function ConsultaConveniosPage() {
  const [parametros, setParametros] = useSearchParams()
  const buscarActivo = parametros.get('buscar') ?? ''
  const pagina = Math.max(1, Number(parametros.get('pagina') ?? '1') || 1)
  const [buscarInput, setBuscarInput] = useState(buscarActivo)

  const filtros = useMemo(
    () => ({
      buscar: buscarActivo || undefined,
      limite: LIMITE,
      desplazamiento: (pagina - 1) * LIMITE,
    }),
    [buscarActivo, pagina],
  )
  const consulta = useConsultaConvenios(filtros)

  const hayFiltros = Boolean(buscarActivo)
  const total = consulta.data?.total ?? 0
  const totalPaginas = Math.max(1, Math.ceil(total / LIMITE))

  function buscar(evento: FormEvent) {
    evento.preventDefault()
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      const termino = buscarInput.trim()
      if (termino) siguientes.set('buscar', termino)
      else siguientes.delete('buscar')
      siguientes.delete('pagina')
      return siguientes
    })
  }

  function limpiarFiltros() {
    setBuscarInput('')
    setParametros({})
  }

  function irAPagina(nueva: number) {
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      if (nueva <= 1) siguientes.delete('pagina')
      else siguientes.set('pagina', String(nueva))
      return siguientes
    })
  }

  const columns: DataTableColumn<ConvenioConsulta>[] = [
    { id: 'codigo', header: 'Código', render: (convenio) => convenio.codigo ?? 'Sin código' },
    {
      id: 'objeto',
      header: 'Objeto',
      render: (convenio) => <span className="convenio-objeto">{convenio.objeto ?? '—'}</span>,
    },
    { id: 'contraparte', header: 'Contraparte', render: contraparte },
    {
      id: 'tipo_convenio',
      header: 'Tipo de convenio',
      render: (convenio) => convenio.tipo_convenio?.nombre ?? '—',
    },
    {
      id: 'estado',
      header: 'Estado',
      render: (convenio) => <StatusBadge value={convenio.estado} />,
    },
    { id: 'etapa', header: 'Etapa', render: (convenio) => convenio.etapa?.nombre ?? 'Sin etapa asignada' },
    {
      id: 'acciones',
      header: 'Acciones',
      render: (convenio) => (
        <Link className="btn btn-outline btn-small" to={`/convenios/${convenio.id}`}>
          Ver
        </Link>
      ),
    },
  ]

  return (
    <>
      <section className="header-banner">
        <h1>Consulta de convenios</h1>
        <p>Busca convenios por código, objeto, aliado o NIT dentro de tu alcance de consulta.</p>
      </section>
      <form onSubmit={buscar}>
        <TableFilters hasActiveFilters={hayFiltros} onClear={limpiarFiltros}>
          <div className="form-group">
            <label className="form-label" htmlFor="buscar-convenio">
              Código, objeto, aliado o NIT
            </label>
            <input
              id="buscar-convenio"
              type="search"
              className="form-control"
              value={buscarInput}
              onChange={(event) => setBuscarInput(event.target.value)}
            />
          </div>
          <div className="form-group table-filter-submit">
            <button className="btn btn-primary" type="submit">
              Buscar
            </button>
          </div>
        </TableFilters>
      </form>

      {consulta.isPending && <p className="estado-pagina">Cargando convenios…</p>}
      {consulta.isError && (
        <p className="alert-error" role="alert">
          {consulta.error instanceof ApiError ? consulta.error.message : 'No se pudo cargar el listado.'}
        </p>
      )}

      {consulta.data && total === 0 && (
        <>
          <ResultsCount count={0} />
          <TableEmptyState
            message={
              hayFiltros
                ? `No se encontraron convenios que coincidan con «${buscarActivo}».`
                : 'No hay convenios visibles para tu rol.'
            }
            onClear={hayFiltros ? limpiarFiltros : undefined}
          />
        </>
      )}

      {consulta.data && total > 0 && (
        <>
          <ResultsCount count={total} />
          <DataTable columns={columns} rows={consulta.data.items} rowKey={(convenio) => convenio.id} label="Convenios" />
          <div className="table-pagination">
            <button
              type="button"
              className="btn btn-outline btn-small"
              disabled={pagina <= 1}
              onClick={() => irAPagina(pagina - 1)}
            >
              Anterior
            </button>
            <span className="table-pagination-info">
              Página {pagina} de {totalPaginas}
            </span>
            <button
              type="button"
              className="btn btn-outline btn-small"
              disabled={pagina >= totalPaginas}
              onClick={() => irAPagina(pagina + 1)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </>
  )
}

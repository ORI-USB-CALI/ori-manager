import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import {
  DataTable,
  ResultsCount,
  TableEmptyState,
  type DataTableColumn,
} from '../components/DataTable'
import { Select } from '../components/Select'
import { TableFilters } from '../components/TableFilters'
import { StatusBadge } from '../components/tablePresentation'
import { ETIQUETA_TIPO, type Aliado, type TipoAliado } from './epica02'

type FiltroEstado = '' | 'activo' | 'inactivo'

export function AliadosPage() {
  const [buscar, setBuscar] = useState('')
  const [consulta, setConsulta] = useState('')
  const [tipo, setTipo] = useState<TipoAliado | ''>('')
  const [estado, setEstado] = useState<FiltroEstado>('')
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

  const hayFiltros = Boolean(consulta || tipo || estado)
  const items = useMemo(
    () =>
      (aliados.data?.items ?? []).filter(
        (aliado) =>
          (!tipo || aliado.tipo === tipo) &&
          (!estado || aliado.activo === (estado === 'activo')),
      ),
    [aliados.data, estado, tipo],
  )

  function limpiarFiltros() {
    setBuscar('')
    setConsulta('')
    setTipo('')
    setEstado('')
  }

  const columns: DataTableColumn<Aliado>[] = [
    { id: 'nombre', header: 'Nombre', render: (aliado) => <strong>{aliado.nombre}</strong> },
    { id: 'identificacion', header: 'NIT / documento', render: (aliado) => aliado.identificacion },
    { id: 'tipo', header: 'Tipo de aliado', render: (aliado) => ETIQUETA_TIPO[aliado.tipo] },
    { id: 'estado', header: 'Estado', render: (aliado) => <StatusBadge value={aliado.activo ? 'ACTIVO' : 'INACTIVO'} label={aliado.activo ? 'Activo' : 'Inactivo'} /> },
    { id: 'acciones', header: 'Acciones', render: (aliado) => <Link className="btn btn-outline btn-small" to={`/aliados/${aliado.id}`}>Ver perfil</Link> },
  ]

  return (
    <>
      <section className="header-banner">
        <h1>Gestión de aliados</h1>
        <p>Consulte las entidades reconocidas al formalizar convenios.</p>
      </section>
      <form onSubmit={filtrar}>
        <TableFilters hasActiveFilters={hayFiltros} onClear={limpiarFiltros}>
          <div className="form-group">
            <label className="form-label" htmlFor="buscar-aliado">Nombre o NIT/documento</label>
            <input id="buscar-aliado" type="search" className="form-control" value={buscar} onChange={(event) => setBuscar(event.target.value)} />
          </div>
          <Select id="aliados-tipo" label="Tipo de aliado" value={tipo} opciones={[{ value: '', label: 'Todos' }, ...Object.entries(ETIQUETA_TIPO).map(([value, label]) => ({ value, label }))]} onChange={(event) => setTipo(event.target.value as TipoAliado | '')} />
          <Select id="aliados-estado" label="Estado" value={estado} opciones={[{ value: '', label: 'Todos' }, { value: 'activo', label: 'Activo' }, { value: 'inactivo', label: 'Inactivo' }]} onChange={(event) => setEstado(event.target.value as FiltroEstado)} />
          <div className="form-group table-filter-submit">
            <button className="btn btn-primary" type="submit">Buscar</button>
          </div>
        </TableFilters>
      </form>
      {aliados.isPending && <p className="estado-pagina">Cargando aliados…</p>}
      {aliados.isError && (
        <p className="alert-error" role="alert">
          {aliados.error instanceof ApiError ? aliados.error.message : 'No se pudo cargar el listado.'}
        </p>
      )}
      {aliados.data?.items.length === 0 && (
        <>
          <ResultsCount count={0} />
          <TableEmptyState
            message={hayFiltros ? 'No se encontraron resultados con los filtros seleccionados.' : 'No hay aliados.'}
            onClear={hayFiltros ? limpiarFiltros : undefined}
          />
        </>
      )}
      {aliados.data && aliados.data.items.length > 0 && (
        <>
          <ResultsCount count={items.length} />
          {items.length > 0 ? (
            <DataTable columns={columns} rows={items} rowKey={(aliado) => aliado.id} label="Aliados" />
          ) : (
            <TableEmptyState message="No se encontraron resultados con los filtros seleccionados." onClear={limpiarFiltros} />
          )}
        </>
      )}
    </>
  )
}

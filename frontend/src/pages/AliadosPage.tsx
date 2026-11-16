import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiFetch } from '../app/api'
import {
  DataTable,
  ResultsCount,
  type DataTableColumn,
} from '../components/DataTable'
import { Select } from '../components/Select'
import { TableFilters } from '../components/TableFilters'
import { StatusBadge } from '../components/tablePresentation'
import { ETIQUETA_TIPO, type Aliado, type TipoAliado, usePaises } from './epica02'

type FiltroEstado = '' | 'activo' | 'inactivo'

export function AliadosPage() {
  const [buscar, setBuscar] = useState('')
  const [consulta, setConsulta] = useState('')
  const [tipo, setTipo] = useState<TipoAliado | ''>('')
  const [estado, setEstado] = useState<FiltroEstado>('')
  const [pais, setPais] = useState('')
  const [pagina, setPagina] = useState(0)
  const paises = usePaises()
  const limite = 20
  const parametros = new URLSearchParams({ limite: String(limite), desplazamiento: String(pagina * limite) })
  if (consulta) parametros.set('buscar', consulta)
  if (tipo) parametros.set('tipo', tipo)
  if (estado) parametros.set('activo', String(estado === 'activo'))
  if (pais) parametros.set('pais_id', pais)
  const aliados = useQuery({
    queryKey: ['aliados', 'listado', consulta, tipo, estado, pais, pagina],
    queryFn: () =>
      apiFetch<{ items: Aliado[]; total: number }>(`/aliados?${parametros}`),
    retry: false,
  })

  function filtrar(evento: FormEvent) {
    evento.preventDefault()
    setConsulta(buscar.trim())
    setPagina(0)
  }

  const hayFiltros = Boolean(consulta || tipo || estado || pais)
  const items = aliados.data?.items ?? []

  function limpiarFiltros() {
    setBuscar('')
    setConsulta('')
    setTipo('')
    setEstado('')
    setPais('')
    setPagina(0)
  }

  const columns: DataTableColumn<Aliado>[] = [
    { id: 'nombre', className: 'tabla-col-persona', header: 'Nombre', render: (aliado) => <strong>{aliado.nombre}</strong> },
    { id: 'identificacion', className: 'tabla-col-referencia', header: 'NIT / documento', render: (aliado) => aliado.identificacion },
    { id: 'pais', className: 'tabla-col-texto', header: 'País', render: (aliado) => aliado.pais_id == null ? 'Sin país' : paises.data?.find((pais) => pais.id === aliado.pais_id)?.nombre ?? 'País no disponible' },
    { id: 'tipo', className: 'tabla-col-texto', header: 'Tipo de aliado', render: (aliado) => ETIQUETA_TIPO[aliado.tipo] },
    { id: 'estado', className: 'tabla-col-estado', header: 'Estado', render: (aliado) => <StatusBadge value={aliado.activo ? 'ACTIVO' : 'INACTIVO'} label={aliado.activo ? 'Activo' : 'Inactivo'} /> },
    { id: 'acciones', className: 'tabla-col-acciones', header: 'Acciones', render: (aliado) => <Link className="btn btn-outline btn-small" to={`/aliados/${aliado.id}`}>Ver perfil</Link> },
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
          <Select id="aliados-tipo" label="Tipo de aliado" value={tipo} opciones={[{ value: '', label: 'Todos' }, ...Object.entries(ETIQUETA_TIPO).map(([value, label]) => ({ value, label }))]} onChange={(event) => { setTipo(event.target.value as TipoAliado | ''); setPagina(0) }} />
          <Select id="aliados-estado" label="Estado" value={estado} opciones={[{ value: '', label: 'Todos' }, { value: 'activo', label: 'Activo' }, { value: 'inactivo', label: 'Inactivo' }]} onChange={(event) => { setEstado(event.target.value as FiltroEstado); setPagina(0) }} />
          <Select id="aliados-pais" label="País" value={pais} opciones={[{ value: '', label: 'Todos' }, ...(paises.data ?? []).map((pais) => ({ value: String(pais.id), label: pais.nombre }))]} onChange={(event) => { setPais(event.target.value); setPagina(0) }} />
          <div className="form-group table-filter-submit">
            <button className="btn btn-primary" type="submit">Buscar</button>
          </div>
        </TableFilters>
      </form>
      {paises.isError && <p className="alert-error" role="alert">No se pudo cargar el catálogo de países.</p>}
      {aliados.isPending && <p className="estado-pagina">Cargando aliados…</p>}
      {aliados.isError && (
        <p className="alert-error" role="alert">
          {aliados.error instanceof ApiError ? aliados.error.message : 'No se pudo cargar el listado.'}
        </p>
      )}
      {aliados.data && (
        <>
          <ResultsCount count={aliados.data.total} />
          <DataTable containerClassName="tabla-densa-region" tableClassName="tabla-densa" columns={columns} rows={items} rowKey={(aliado) => aliado.id} label="Aliados"
            emptyMessage={hayFiltros ? 'No se encontraron resultados con los filtros seleccionados.' : 'No hay aliados.'}
            onClearEmpty={hayFiltros ? limpiarFiltros : undefined} />
          <nav className="table-filters-actions" aria-label="Paginación de aliados">
            <button type="button" className="btn btn-outline btn-small" disabled={pagina === 0 || aliados.isFetching} onClick={() => setPagina(pagina - 1)}>Anterior</button>
            <span aria-live="polite">Página {pagina + 1} de {Math.max(1, Math.ceil(aliados.data.total / limite))}</span>
            <button type="button" className="btn btn-outline btn-small" disabled={(pagina + 1) * limite >= aliados.data.total || aliados.isFetching} onClick={() => setPagina(pagina + 1)}>Siguiente</button>
          </nav>
        </>
      )}
    </>
  )
}

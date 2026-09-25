import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../app/api'
import {
  DataTable,
  ResultsCount,
  TableEmptyState,
  type DataTableColumn,
} from '../components/DataTable'
import { Select } from '../components/Select'
import { TableFilters } from '../components/TableFilters'
import { formatDateTime } from '../components/tableFormatters'

interface RevisionJuridicaPendiente {
  revision_id: number
  convenio_id: number
  codigo_convenio: string | null
  solicitud_consecutivo: string
  objeto: string | null
  tipo_convenio: { id: number; nombre: string } | null
  responsable: { id: number; nombre_completo: string; correo: string }
  fecha_recepcion: string
}

export function RevisionesJuridicasPage() {
  const [busqueda, setBusqueda] = useState('')
  const [tipoConvenio, setTipoConvenio] = useState('')
  const [responsable, setResponsable] = useState('')
  const consulta = useQuery({
    queryKey: ['revisiones-juridicas', 'pendientes'],
    queryFn: () => apiFetch<RevisionJuridicaPendiente[]>('/convenios/revisiones-juridicas/pendientes'),
    retry: false,
  })
  const tiposConvenio = useMemo(
    () =>
      [...new Set((consulta.data ?? []).map((item) => item.tipo_convenio?.nombre).filter(Boolean) as string[])].sort((a, b) => a.localeCompare(b, 'es')),
    [consulta.data],
  )
  const responsables = useMemo(() => {
    const opciones = new Map<number, string>()
    for (const item of consulta.data ?? []) {
      opciones.set(item.responsable.id, item.responsable.nombre_completo)
    }
    return [...opciones.entries()].sort((a, b) => a[1].localeCompare(b[1], 'es'))
  }, [consulta.data])
  const hayFiltros = Boolean(busqueda.trim() || tipoConvenio || responsable)
  const items = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase('es')
    return (consulta.data ?? []).filter((item) => {
      const texto = `${item.codigo_convenio ?? item.convenio_id} ${item.solicitud_consecutivo} ${item.objeto ?? ''} ${item.responsable.nombre_completo} ${item.responsable.correo}`.toLocaleLowerCase('es')
      return (
        (!termino || texto.includes(termino)) &&
        (!tipoConvenio || item.tipo_convenio?.nombre === tipoConvenio) &&
        (!responsable || item.responsable.id === Number(responsable))
      )
    })
  }, [busqueda, consulta.data, responsable, tipoConvenio])

  function limpiarFiltros() {
    setBusqueda('')
    setTipoConvenio('')
    setResponsable('')
  }

  const columns: DataTableColumn<RevisionJuridicaPendiente>[] = [
    { id: 'convenio', header: 'Convenio', render: (item) => <strong>{item.codigo_convenio ?? `#${item.convenio_id}`}</strong> },
    { id: 'solicitud', header: 'Solicitud origen', render: (item) => item.solicitud_consecutivo },
    { id: 'objeto', header: 'Objeto', className: 'table-cell-wide', render: (item) => item.objeto ?? '—' },
    { id: 'tipo', header: 'Tipo convenio', render: (item) => item.tipo_convenio?.nombre ?? '—' },
    {
      id: 'responsable',
      header: 'Responsable',
      render: (item) => (
        <>
          {item.responsable.nombre_completo}
          <small className="tabla-ayuda">{item.responsable.correo}</small>
        </>
      ),
    },
    { id: 'fecha', header: 'Fecha de recepción', render: (item) => formatDateTime(item.fecha_recepcion) },
    { id: 'acciones', header: 'Acciones', render: (item) => <Link className="btn btn-outline btn-small" to={`/convenios/${item.convenio_id}`}>Revisar</Link> },
  ]

  return (
    <>
      <section className="header-banner">
        <h1>Revisiones jurídicas</h1>
        <p>Convenios pendientes de revisión y aval jurídico.</p>
      </section>
      {consulta.isPending && <p className="estado-pagina">Cargando revisiones jurídicas…</p>}
      {consulta.isError && <p className="alert-error" role="alert">{consulta.error.message}</p>}
      {consulta.data?.length === 0 && (
        <>
          <ResultsCount count={0} />
          <TableEmptyState message="No hay revisiones jurídicas pendientes." />
        </>
      )}
      {consulta.data && consulta.data.length > 0 && (
        <>
          <TableFilters hasActiveFilters={hayFiltros} onClear={limpiarFiltros}>
            <div className="form-group">
              <label className="form-label" htmlFor="revisiones-busqueda">Buscar</label>
              <input id="revisiones-busqueda" type="search" className="form-control" placeholder="Convenio, solicitud, objeto o responsable" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} />
            </div>
            <Select id="revisiones-tipo" label="Tipo convenio" value={tipoConvenio} opciones={[{ value: '', label: 'Todos' }, ...tiposConvenio.map((value) => ({ value, label: value }))]} onChange={(event) => setTipoConvenio(event.target.value)} />
            <Select id="revisiones-responsable" label="Responsable" value={responsable} opciones={[{ value: '', label: 'Todos' }, ...responsables.map(([value, label]) => ({ value: String(value), label }))]} onChange={(event) => setResponsable(event.target.value)} />
          </TableFilters>
          <ResultsCount count={items.length} />
          {items.length > 0 ? (
            <DataTable columns={columns} rows={items} rowKey={(item) => item.revision_id} label="Revisiones jurídicas" />
          ) : (
            <TableEmptyState message="No se encontraron resultados con los filtros seleccionados." onClear={limpiarFiltros} />
          )}
        </>
      )}
    </>
  )
}

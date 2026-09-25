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
import { enumLabel, formatDateTime } from '../components/tableFormatters'
import { StatusBadge } from '../components/tablePresentation'
import {
  type EstadoSolicitud,
  type Solicitud,
  useCatalogosSolicitud,
} from './solicitudes'

const ESTADOS: EstadoSolicitud[] = [
  'BORRADOR',
  'RADICADA',
  'EN_ESTUDIO',
  'DEVUELTA',
  'APROBADA',
  'RECHAZADA',
]

export function MisSolicitudesPage() {
  const [busqueda, setBusqueda] = useState('')
  const [estado, setEstado] = useState<EstadoSolicitud | ''>('')
  const [tipoConvenio, setTipoConvenio] = useState('')
  const consulta = useQuery({
    queryKey: ['solicitudes', 'mias'],
    queryFn: () =>
      apiFetch<{ items: Solicitud[]; total: number }>('/solicitudes/mias'),
    retry: false,
  })
  const catalogos = useCatalogosSolicitud()
  const nombresTipo = useMemo(
    () =>
      new Map(
        (catalogos.data?.tipos_convenio ?? []).map((tipo) => [
          tipo.id,
          tipo.nombre,
        ]),
      ),
    [catalogos.data],
  )
  const hayFiltros = Boolean(busqueda.trim() || estado || tipoConvenio)
  const items = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase('es')
    return (consulta.data?.items ?? []).filter((item) => {
      const coincideBusqueda =
        !termino ||
        `${item.consecutivo} ${item.nombre_aliado_propuesto ?? ''}`
          .toLocaleLowerCase('es')
          .includes(termino)
      return (
        coincideBusqueda &&
        (!estado || item.estado === estado) &&
        (!tipoConvenio || item.tipo_convenio_id === Number(tipoConvenio))
      )
    })
  }, [busqueda, consulta.data, estado, tipoConvenio])

  function limpiarFiltros() {
    setBusqueda('')
    setEstado('')
    setTipoConvenio('')
  }

  const columns: DataTableColumn<Solicitud>[] = [
    {
      id: 'consecutivo',
      header: 'Consecutivo',
      render: (item) => <strong>{item.consecutivo}</strong>,
    },
    {
      id: 'contraparte',
      header: 'Contraparte',
      render: (item) => item.nombre_aliado_propuesto ?? '—',
    },
    {
      id: 'tipo',
      header: 'Tipo de convenio',
      render: (item) =>
        item.tipo_convenio_id
          ? (nombresTipo.get(item.tipo_convenio_id) ?? '—')
          : '—',
    },
    {
      id: 'estado',
      header: 'Estado solicitud',
      render: (item) => <StatusBadge value={item.estado} />,
    },
    {
      id: 'radicacion',
      header: 'Radicación',
      render: (item) => formatDateTime(item.fecha_radicacion),
    },
    {
      id: 'acciones',
      header: 'Acciones',
      render: (item) => (
        <Link
          className="btn btn-outline btn-small"
          to={`/solicitudes/${item.id}`}
        >
          Ver
        </Link>
      ),
    },
  ]

  return (
    <>
      <section className="header-banner">
        <h1>Mis solicitudes</h1>
        <p>Consulte sus borradores y solicitudes radicadas.</p>
      </section>
      <div className="page-toolbar">
        <Link className="btn btn-primary" to="/solicitudes/nueva">
          Nueva solicitud
        </Link>
      </div>
      {consulta.isPending && (
        <p className="estado-pagina">Cargando solicitudes…</p>
      )}
      {consulta.isError && (
        <p className="alert-error" role="alert">
          {consulta.error.message}
        </p>
      )}
      {consulta.data && consulta.data.items.length === 0 && (
        <>
          <ResultsCount count={0} />
          <TableEmptyState message="Aún no tiene solicitudes." />
        </>
      )}
      {consulta.data && consulta.data.items.length > 0 && (
        <>
          <TableFilters
            hasActiveFilters={hayFiltros}
            onClear={limpiarFiltros}
          >
            <div className="form-group">
              <label
                className="form-label"
                htmlFor="mis-solicitudes-busqueda"
              >
                Buscar
              </label>
              <input
                id="mis-solicitudes-busqueda"
                type="search"
                className="form-control"
                placeholder="Consecutivo o contraparte"
                value={busqueda}
                onChange={(event) => setBusqueda(event.target.value)}
              />
            </div>
            <Select
              id="mis-solicitudes-estado"
              label="Estado solicitud"
              value={estado}
              opciones={[
                { value: '', label: 'Todos' },
                ...ESTADOS.map((value) => ({
                  value,
                  label: enumLabel(value),
                })),
              ]}
              onChange={(event) =>
                setEstado(event.target.value as EstadoSolicitud | '')
              }
            />
            <Select
              id="mis-solicitudes-tipo"
              label="Tipo de convenio"
              value={tipoConvenio}
              opciones={[
                { value: '', label: 'Todos' },
                ...(catalogos.data?.tipos_convenio ?? []).map((tipo) => ({
                  value: String(tipo.id),
                  label: tipo.nombre,
                })),
              ]}
              onChange={(event) => setTipoConvenio(event.target.value)}
            />
          </TableFilters>
          <ResultsCount count={items.length} />
          {items.length > 0 ? (
            <DataTable
              columns={columns}
              rows={items}
              rowKey={(item) => item.id}
              label="Mis solicitudes"
            />
          ) : (
            <TableEmptyState
              message="No se encontraron resultados con los filtros seleccionados."
              onClear={limpiarFiltros}
            />
          )}
        </>
      )}
    </>
  )
}

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
import type { TipoUsuario } from '../auth/sesion'
import type { EstadoSolicitud, SolicitudRecibida } from './solicitudes'

const ESTADOS: EstadoSolicitud[] = ['RADICADA', 'EN_ESTUDIO', 'APROBADA', 'DEVUELTA', 'RECHAZADA']

export function SolicitudesRecibidasPage() {
  const [busqueda, setBusqueda] = useState('')
  const [estado, setEstado] = useState<EstadoSolicitud | ''>('')
  const [etapa, setEtapa] = useState('')
  const [tipoSolicitante, setTipoSolicitante] = useState<TipoUsuario | ''>('')
  const [tipoConvenio, setTipoConvenio] = useState('')
  const consulta = useQuery({
    queryKey: ['solicitudes', 'recibidas'],
    queryFn: () => apiFetch<{ items: SolicitudRecibida[]; total: number }>('/solicitudes/recibidas'),
    retry: false,
  })
  const etapas = useMemo(() => {
    const opciones = new Map<string, string>()
    for (const item of consulta.data?.items ?? []) {
      if (item.convenio_etapa) {
        opciones.set(item.convenio_etapa.codigo, item.convenio_etapa.nombre)
      }
    }
    return [...opciones.entries()].sort((a, b) => a[1].localeCompare(b[1], 'es'))
  }, [consulta.data])
  const tiposConvenio = useMemo(
    () =>
      [...new Set((consulta.data?.items ?? []).map((item) => item.tipo_convenio_nombre).filter(Boolean) as string[])].sort((a, b) => a.localeCompare(b, 'es')),
    [consulta.data],
  )
  const hayFiltros = Boolean(
    busqueda.trim() || estado || etapa || tipoSolicitante || tipoConvenio,
  )
  const items = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase('es')
    return (consulta.data?.items ?? []).filter((item) => {
      const texto = `${item.consecutivo} ${item.solicitante_nombre ?? ''} ${item.solicitante_correo ?? ''} ${item.nombre_aliado_propuesto ?? ''}`.toLocaleLowerCase('es')
      const coincideEtapa =
        !etapa ||
        (etapa === 'SIN_CONVENIO'
          ? item.convenio_id === null
          : item.convenio_etapa?.codigo === etapa)
      return (
        (!termino || texto.includes(termino)) &&
        (!estado || item.estado === estado) &&
        coincideEtapa &&
        (!tipoSolicitante || item.tipo_solicitante === tipoSolicitante) &&
        (!tipoConvenio || item.tipo_convenio_nombre === tipoConvenio)
      )
    })
  }, [busqueda, consulta.data, estado, etapa, tipoConvenio, tipoSolicitante])

  function limpiarFiltros() {
    setBusqueda('')
    setEstado('')
    setEtapa('')
    setTipoSolicitante('')
    setTipoConvenio('')
  }

  const columns: DataTableColumn<SolicitudRecibida>[] = [
    { id: 'consecutivo', header: 'Consecutivo', render: (item) => <strong>{item.consecutivo}</strong> },
    {
      id: 'solicitante',
      header: 'Solicitante',
      render: (item) => (
        <>
          {item.solicitante_nombre ?? item.solicitante_correo ?? '—'}
          {item.solicitante_nombre && item.solicitante_correo && (
            <small className="tabla-ayuda">{item.solicitante_correo}</small>
          )}
        </>
      ),
    },
    { id: 'contraparte', header: 'Contraparte', render: (item) => item.nombre_aliado_propuesto ?? '—' },
    { id: 'tipo', header: 'Tipo convenio', render: (item) => item.tipo_convenio_nombre ?? '—' },
    { id: 'estado-solicitud', header: 'Estado solicitud', render: (item) => <StatusBadge value={item.estado} /> },
    {
      id: 'etapa-convenio',
      header: 'Etapa convenio',
      render: (item) => item.convenio_etapa ? <StatusBadge value={item.convenio_etapa.codigo} label={item.convenio_etapa.nombre} /> : '—',
    },
    { id: 'estado-convenio', header: 'Estado convenio', render: (item) => item.convenio_estado ? <StatusBadge value={item.convenio_estado} /> : '—' },
    { id: 'radicacion', header: 'Radicación', render: (item) => formatDateTime(item.fecha_radicacion) },
    { id: 'acciones', header: 'Acciones', render: (item) => <Link className="btn btn-outline btn-small" to={`/ori/solicitudes/${item.id}`}>Ver</Link> },
  ]

  return (
    <>
      <section className="header-banner">
        <h1>Solicitudes recibidas</h1>
        <p>Bandeja operativa de solicitudes radicadas ante la ORI.</p>
      </section>
      {consulta.isPending && <p className="estado-pagina">Cargando solicitudes recibidas…</p>}
      {consulta.isError && <p className="alert-error" role="alert">{consulta.error.message}</p>}
      {consulta.data?.items.length === 0 && (
        <>
          <ResultsCount count={0} />
          <TableEmptyState message="No hay solicitudes recibidas." />
        </>
      )}
      {consulta.data && consulta.data.items.length > 0 && (
        <>
          <TableFilters hasActiveFilters={hayFiltros} onClear={limpiarFiltros}>
            <div className="form-group">
              <label className="form-label" htmlFor="solicitudes-recibidas-busqueda">Buscar</label>
              <input id="solicitudes-recibidas-busqueda" type="search" className="form-control" placeholder="Consecutivo, solicitante o contraparte" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} />
            </div>
            <Select id="solicitudes-recibidas-estado" label="Estado solicitud" value={estado} opciones={[{ value: '', label: 'Todos' }, ...ESTADOS.map((value) => ({ value, label: enumLabel(value) }))]} onChange={(event) => setEstado(event.target.value as EstadoSolicitud | '')} />
            <Select id="solicitudes-recibidas-etapa" label="Etapa convenio" value={etapa} opciones={[{ value: '', label: 'Todas' }, { value: 'SIN_CONVENIO', label: 'Sin convenio' }, ...etapas.map(([value, label]) => ({ value, label }))]} onChange={(event) => setEtapa(event.target.value)} />
            <Select id="solicitudes-recibidas-solicitante" label="Tipo solicitante" value={tipoSolicitante} opciones={[{ value: '', label: 'Todos' }, { value: 'INTERNO', label: 'Interno' }, { value: 'EXTERNO', label: 'Externo' }]} onChange={(event) => setTipoSolicitante(event.target.value as TipoUsuario | '')} />
            <Select id="solicitudes-recibidas-tipo" label="Tipo convenio" value={tipoConvenio} opciones={[{ value: '', label: 'Todos' }, ...tiposConvenio.map((value) => ({ value, label: value }))]} onChange={(event) => setTipoConvenio(event.target.value)} />
          </TableFilters>
          <ResultsCount count={items.length} />
          {items.length > 0 ? (
            <DataTable columns={columns} rows={items} rowKey={(item) => item.id} label="Solicitudes recibidas" />
          ) : (
            <TableEmptyState message="No se encontraron resultados con los filtros seleccionados." onClear={limpiarFiltros} />
          )}
        </>
      )}
    </>
  )
}

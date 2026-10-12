import { type FormEvent, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError } from '../app/api'
import {
  DataTable,
  ResultsCount,
  TableEmptyState,
  type DataTableColumn,
} from '../components/DataTable'
import { FiltroFechas } from '../components/FiltroFechas'
import { TableFilters } from '../components/TableFilters'
import { StatusBadge } from '../components/tablePresentation'
import { formatDate } from '../components/tableFormatters'
import { type ConvenioConsulta, type TipoFiltroFecha, useConsultaConvenios } from './consultaConvenios'
import { ETIQUETA_TIPO } from './epica02'

const TIPO_FECHA_DEFECTO: TipoFiltroFecha = 'FORMALIZACION'

function esTipoFiltroFecha(valor: string | null): valor is TipoFiltroFecha {
  return valor === 'FORMALIZACION' || valor === 'VIGENCIA'
}

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
  const tipoFechaActivo = esTipoFiltroFecha(parametros.get('tipo_fecha'))
    ? (parametros.get('tipo_fecha') as TipoFiltroFecha)
    : TIPO_FECHA_DEFECTO
  const fechaDesdeActivo = parametros.get('fecha_desde') ?? ''
  const fechaHastaActivo = parametros.get('fecha_hasta') ?? ''
  const pagina = Math.max(1, Number(parametros.get('pagina') ?? '1') || 1)
  const [buscarInput, setBuscarInput] = useState(buscarActivo)
  const [tipoFechaInput, setTipoFechaInput] = useState<TipoFiltroFecha>(tipoFechaActivo)
  const [fechaDesdeInput, setFechaDesdeInput] = useState(fechaDesdeActivo)
  const [fechaHastaInput, setFechaHastaInput] = useState(fechaHastaActivo)

  // CA-05/RN-07: desde > hasta no se envía ni se refleja en la URL.
  const rangoInvalido = Boolean(
    fechaDesdeInput && fechaHastaInput && fechaDesdeInput > fechaHastaInput,
  )

  const filtros = useMemo(
    () => ({
      buscar: buscarActivo || undefined,
      limite: LIMITE,
      desplazamiento: (pagina - 1) * LIMITE,
      tipo_fecha: tipoFechaActivo,
      fecha_desde: fechaDesdeActivo || undefined,
      fecha_hasta: fechaHastaActivo || undefined,
    }),
    [buscarActivo, pagina, tipoFechaActivo, fechaDesdeActivo, fechaHastaActivo],
  )
  const consulta = useConsultaConvenios(filtros)

  const hayFiltros = Boolean(buscarActivo || fechaDesdeActivo || fechaHastaActivo)
  const total = consulta.data?.total ?? 0
  const totalPaginas = Math.max(1, Math.ceil(total / LIMITE))

  function buscar(evento: FormEvent) {
    evento.preventDefault()
    if (rangoInvalido) return
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      const termino = buscarInput.trim()
      if (termino) siguientes.set('buscar', termino)
      else siguientes.delete('buscar')
      if (fechaDesdeInput || fechaHastaInput) {
        siguientes.set('tipo_fecha', tipoFechaInput)
        if (fechaDesdeInput) siguientes.set('fecha_desde', fechaDesdeInput)
        else siguientes.delete('fecha_desde')
        if (fechaHastaInput) siguientes.set('fecha_hasta', fechaHastaInput)
        else siguientes.delete('fecha_hasta')
      } else {
        siguientes.delete('tipo_fecha')
        siguientes.delete('fecha_desde')
        siguientes.delete('fecha_hasta')
      }
      siguientes.delete('pagina')
      return siguientes
    })
  }

  function limpiarFiltros() {
    setBuscarInput('')
    setTipoFechaInput(TIPO_FECHA_DEFECTO)
    setFechaDesdeInput('')
    setFechaHastaInput('')
    setParametros({})
  }

  // FE-4: "Quitar fechas" solo limpia el rango (no el término de búsqueda) y
  // se aplica de inmediato, sin pasar por el botón Buscar — RN-08: es una
  // simple relectura con otros query params, no escribe nada en el backend.
  function quitarFechas() {
    setTipoFechaInput(TIPO_FECHA_DEFECTO)
    setFechaDesdeInput('')
    setFechaHastaInput('')
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      siguientes.delete('tipo_fecha')
      siguientes.delete('fecha_desde')
      siguientes.delete('fecha_hasta')
      siguientes.delete('pagina')
      return siguientes
    })
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
      id: 'formalizacion',
      header: 'Formalización',
      // La regla de qué cuenta como formalizado vive solo en el backend
      // (HU-27 BE-2): aquí simplemente se muestra null como "Sin formalizar".
      render: (convenio) =>
        convenio.fecha_formalizacion ? formatDate(convenio.fecha_formalizacion) : 'Sin formalizar',
    },
    {
      id: 'vigencia',
      header: 'Vigencia',
      render: (convenio) =>
        convenio.fecha_inicio
          ? `${formatDate(convenio.fecha_inicio)} – ${
              convenio.fecha_vencimiento ? formatDate(convenio.fecha_vencimiento) : 'sin vencimiento'
            }`
          : 'Sin definir',
    },
    {
      id: 'acciones',
      header: 'Acciones',
      render: (convenio) => (
        <Link
          className="btn btn-outline btn-small"
          to={convenio.puede_ver_detalle
            ? `/convenios/${convenio.id}`
            : `/convenios/${convenio.id}/historial`}
        >
          {convenio.puede_ver_detalle ? 'Ver' : 'Ver historial'}
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
          <FiltroFechas
            tipoFecha={tipoFechaInput}
            fechaDesde={fechaDesdeInput}
            fechaHasta={fechaHastaInput}
            invalido={rangoInvalido}
            onTipoFechaChange={setTipoFechaInput}
            onFechaDesdeChange={setFechaDesdeInput}
            onFechaHastaChange={setFechaHastaInput}
            onQuitarFechas={quitarFechas}
          />
          <div className="form-group table-filter-submit">
            <button className="btn btn-primary" type="submit" disabled={rangoInvalido}>
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

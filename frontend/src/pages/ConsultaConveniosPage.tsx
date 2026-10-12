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
import { FiltrosAvanzados } from '../components/FiltrosAvanzados'
import { TableFilters } from '../components/TableFilters'
import { StatusBadge } from '../components/tablePresentation'
import { enumLabel, formatDate } from '../components/tableFormatters'
import {
  type ConvenioConsulta,
  type TipoFiltroFecha,
  useCatalogosConsulta,
  useConsultaConvenios,
} from './consultaConvenios'
import { ETIQUETA_TIPO, type EstadoConvenio, type TipoAliado } from './epica02'

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
  // getAll() crea un arreglo nuevo en cada render; se memoiza por URL para
  // que `filtros` (y la query key) solo cambie cuando cambia la URL.
  const estadosActivos = useMemo(
    () => parametros.getAll('estado') as EstadoConvenio[],
    [parametros],
  )
  const tiposContraparteActivos = useMemo(
    () => parametros.getAll('tipo_contraparte') as TipoAliado[],
    [parametros],
  )
  const programaIdActivo = parametros.get('programa_id') ?? ''
  const pagina = Math.max(1, Number(parametros.get('pagina') ?? '1') || 1)
  const [buscarInput, setBuscarInput] = useState(buscarActivo)
  const [tipoFechaInput, setTipoFechaInput] = useState<TipoFiltroFecha>(tipoFechaActivo)
  const [fechaDesdeInput, setFechaDesdeInput] = useState(fechaDesdeActivo)
  const [fechaHastaInput, setFechaHastaInput] = useState(fechaHastaActivo)
  const [estadosInput, setEstadosInput] = useState<EstadoConvenio[]>(estadosActivos)
  const [tiposContraparteInput, setTiposContraparteInput] = useState<TipoAliado[]>(tiposContraparteActivos)
  const [programaIdInput, setProgramaIdInput] = useState(programaIdActivo)
  const claveFiltros = JSON.stringify([
    buscarActivo, tipoFechaActivo, fechaDesdeActivo, fechaHastaActivo,
    estadosActivos, tiposContraparteActivos, programaIdActivo,
  ])
  const [claveAnterior, setClaveAnterior] = useState(claveFiltros)
  if (claveAnterior !== claveFiltros) {
    setClaveAnterior(claveFiltros)
    setBuscarInput(buscarActivo)
    setTipoFechaInput(tipoFechaActivo)
    setFechaDesdeInput(fechaDesdeActivo)
    setFechaHastaInput(fechaHastaActivo)
    setEstadosInput(estadosActivos)
    setTiposContraparteInput(tiposContraparteActivos)
    setProgramaIdInput(programaIdActivo)
  }
  const catalogos = useCatalogosConsulta()
  // Fechas y filtros avanzados van plegados; se abren solos si la URL ya trae alguno.
  const cantidadFiltrosAdicionales =
    (fechaDesdeActivo || fechaHastaActivo ? 1 : 0) +
    estadosActivos.length +
    tiposContraparteActivos.length +
    (programaIdActivo ? 1 : 0)
  const [mostrarFiltros, setMostrarFiltros] = useState(cantidadFiltrosAdicionales > 0)

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
      estados: estadosActivos.length > 0 ? estadosActivos : undefined,
      tipos_contraparte: tiposContraparteActivos.length > 0 ? tiposContraparteActivos : undefined,
      programa_id: programaIdActivo ? Number(programaIdActivo) : undefined,
    }),
    [
      buscarActivo,
      pagina,
      tipoFechaActivo,
      fechaDesdeActivo,
      fechaHastaActivo,
      estadosActivos,
      tiposContraparteActivos,
      programaIdActivo,
    ],
  )
  const consulta = useConsultaConvenios(filtros)

  const hayFiltros = Boolean(
    buscarActivo ||
      fechaDesdeActivo ||
      fechaHastaActivo ||
      estadosActivos.length > 0 ||
      tiposContraparteActivos.length > 0 ||
      programaIdActivo,
  )
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
      siguientes.delete('estado')
      estadosInput.forEach((estado) => siguientes.append('estado', estado))
      siguientes.delete('tipo_contraparte')
      tiposContraparteInput.forEach((tipo) => siguientes.append('tipo_contraparte', tipo))
      if (programaIdInput) siguientes.set('programa_id', programaIdInput)
      else siguientes.delete('programa_id')
      siguientes.delete('pagina')
      return siguientes
    })
  }

  function limpiarFiltros() {
    setBuscarInput('')
    setTipoFechaInput(TIPO_FECHA_DEFECTO)
    setFechaDesdeInput('')
    setFechaHastaInput('')
    setEstadosInput([])
    setTiposContraparteInput([])
    setProgramaIdInput('')
    setParametros({})
  }

  // FE-5: cada chip se quita de inmediato (sin pasar por el botón Buscar),
  // igual que quitarFechas — RN-08: es una relectura, no una escritura.
  function quitarBusqueda() {
    setBuscarInput('')
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      siguientes.delete('buscar')
      siguientes.delete('pagina')
      return siguientes
    })
  }

  // La URL se recalcula desde los filtros aplicados (no desde las casillas):
  // quitar un chip no debe aplicar casillas marcadas sin pulsar Buscar.
  function quitarEstado(estado: EstadoConvenio) {
    const restantes = estadosActivos.filter((item) => item !== estado)
    setEstadosInput((actuales) => actuales.filter((item) => item !== estado))
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      siguientes.delete('estado')
      restantes.forEach((item) => siguientes.append('estado', item))
      siguientes.delete('pagina')
      return siguientes
    })
  }

  function quitarTipoContraparte(tipo: TipoAliado) {
    const restantes = tiposContraparteActivos.filter((item) => item !== tipo)
    setTiposContraparteInput((actuales) => actuales.filter((item) => item !== tipo))
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      siguientes.delete('tipo_contraparte')
      restantes.forEach((item) => siguientes.append('tipo_contraparte', item))
      siguientes.delete('pagina')
      return siguientes
    })
  }

  function quitarPrograma() {
    setProgramaIdInput('')
    setParametros((previos) => {
      const siguientes = new URLSearchParams(previos)
      siguientes.delete('programa_id')
      siguientes.delete('pagina')
      return siguientes
    })
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

  // HU-28 FE-5: un chip por filtro activo, cada uno removible individualmente.
  const programaActivo = catalogos.data?.programas.find(
    (programa) => String(programa.id) === programaIdActivo,
  )
  const chips: { key: string; label: string; onRemove: () => void }[] = []
  if (buscarActivo) {
    chips.push({ key: 'buscar', label: `Búsqueda: «${buscarActivo}»`, onRemove: quitarBusqueda })
  }
  if (fechaDesdeActivo || fechaHastaActivo) {
    const criterio = tipoFechaActivo === 'FORMALIZACION' ? 'Formalización' : 'Vigencia'
    chips.push({
      key: 'fechas',
      label: `${criterio}: ${fechaDesdeActivo ? formatDate(fechaDesdeActivo) : '…'} – ${
        fechaHastaActivo ? formatDate(fechaHastaActivo) : '…'
      }`,
      onRemove: quitarFechas,
    })
  }
  estadosActivos.forEach((estado) => {
    chips.push({ key: `estado-${estado}`, label: enumLabel(estado), onRemove: () => quitarEstado(estado) })
  })
  tiposContraparteActivos.forEach((tipo) => {
    chips.push({
      key: `tipo-${tipo}`,
      label: ETIQUETA_TIPO[tipo],
      onRemove: () => quitarTipoContraparte(tipo),
    })
  })
  if (programaIdActivo) {
    chips.push({
      key: 'programa',
      label: programaActivo?.nombre ?? 'Programa',
      onRemove: quitarPrograma,
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
          {/* Tres filas a todo el ancho: la grilla automática de TableFilters
              apretaba los filtros de HU-27/HU-28 en columnas de 160px. */}
          <div className="consulta-fila consulta-fila-busqueda">
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
            <button
              type="button"
              className="btn btn-outline"
              aria-expanded={mostrarFiltros}
              aria-controls="consulta-filtros-adicionales"
              onClick={() => setMostrarFiltros((abierto) => !abierto)}
            >
              {mostrarFiltros ? 'Menos filtros' : 'Más filtros'}
              {cantidadFiltrosAdicionales > 0 && ` (${cantidadFiltrosAdicionales})`}
            </button>
            <button className="btn btn-primary" type="submit" disabled={rangoInvalido}>
              Buscar
            </button>
          </div>
          {/* Un rango inválido deja Buscar deshabilitado: el error no puede quedar oculto. */}
          {(mostrarFiltros || rangoInvalido) && (
            <div id="consulta-filtros-adicionales" className="consulta-filtros-adicionales">
              <div className="consulta-fila">
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
              </div>
              <div className="consulta-fila consulta-fila-avanzados">
                <FiltrosAvanzados
                  catalogos={catalogos.data}
                  estados={estadosInput}
                  tiposContraparte={tiposContraparteInput}
                  programaId={programaIdInput}
                  onEstadosChange={setEstadosInput}
                  onTiposContraparteChange={setTiposContraparteInput}
                  onProgramaIdChange={setProgramaIdInput}
                />
              </div>
            </div>
          )}
        </TableFilters>
      </form>

      {chips.length > 0 && (
        <ul className="filtros-chips" aria-label="Filtros activos">
          {chips.map((chip) => (
            <li key={chip.key} className="filtro-chip">
              {chip.label}
              <button
                type="button"
                className="filtro-chip-quitar"
                aria-label={`Quitar filtro: ${chip.label}`}
                onClick={chip.onRemove}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

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
              buscarActivo
                ? `No se encontraron convenios que coincidan con «${buscarActivo}».`
                : hayFiltros
                  ? 'No hay convenios que cumplan los filtros seleccionados.'
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

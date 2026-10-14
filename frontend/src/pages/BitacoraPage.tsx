import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '../app/api'
import { ETIQUETAS_ROL, type CodigoRol, useSesion } from '../auth/sesion'
import {
  DataTable,
  ResultsCount,
  type DataTableColumn,
} from '../components/DataTable'
import { Select } from '../components/Select'
import { TableFilters } from '../components/TableFilters'
import { formatDateTime } from '../components/tableFormatters'
import { StatusBadge } from '../components/tablePresentation'
import {
  ETIQUETAS_ACCION,
  FILTROS_BITACORA_VACIOS,
  LONGITUD_MAXIMA_ENTIDAD,
  TAMANO_PAGINA_BITACORA,
  hayFiltrosBitacora,
  rangoFechasInvalido,
  useBitacora,
  type AccionBitacora,
  type FiltrosBitacora,
  type RegistroBitacora,
} from './bitacora'

function valor(texto: string | null) {
  return texto?.trim() ? texto : '—'
}

function etiquetaRol(rol: string | null) {
  if (!rol) return '—'
  return ETIQUETAS_ROL[rol as CodigoRol] ?? rol
}

const COLUMNAS: DataTableColumn<RegistroBitacora>[] = [
  { id: 'fecha', header: 'Fecha y hora', render: (fila) => formatDateTime(fila.fecha_hora) },
  {
    id: 'usuario',
    header: 'Usuario',
    render: (fila) => (
      <>
        <strong>{fila.usuario.nombre_completo}</strong>
        <small className="tabla-ayuda">{fila.usuario.correo}</small>
      </>
    ),
  },
  { id: 'rol', header: 'Rol', render: (fila) => etiquetaRol(fila.rol) },
  {
    id: 'accion',
    header: 'Acción',
    render: (fila) => <StatusBadge value={fila.accion} label={ETIQUETAS_ACCION[fila.accion]} />,
  },
  { id: 'registro', header: 'Registro afectado', render: (fila) => `${fila.entidad} #${fila.registro_id}` },
  { id: 'campo', header: 'Campo', render: (fila) => valor(fila.campo) },
  { id: 'anterior', header: 'Valor anterior', render: (fila) => valor(fila.valor_anterior) },
  { id: 'nuevo', header: 'Valor nuevo', render: (fila) => valor(fila.valor_nuevo) },
  { id: 'contexto', header: 'Contexto', render: (fila) => valor(fila.contexto) },
]

function AccesoDenegado() {
  return (
    <section className="card estado-vacio">
      <h1>Acceso denegado</h1>
      <p>No tiene permiso para consultar la bitácora de cambios.</p>
      <Link to="/" className="btn btn-outline">
        Volver al inicio
      </Link>
    </section>
  )
}

export function BitacoraPage() {
  const { puede } = useSesion()
  const autorizado = puede('auditoria.ver')
  const [borrador, setBorrador] = useState<FiltrosBitacora>(FILTROS_BITACORA_VACIOS)
  const [aplicados, setAplicados] = useState<FiltrosBitacora>(FILTROS_BITACORA_VACIOS)
  const [pagina, setPagina] = useState(1)
  const consulta = useBitacora(aplicados, pagina, autorizado)

  if (!autorizado) return <AccesoDenegado />
  if (consulta.error instanceof ApiError && consulta.error.status === 403) {
    return <AccesoDenegado />
  }

  const rangoInvalido = rangoFechasInvalido(borrador)
  const hayFiltros = hayFiltrosBitacora(aplicados)

  function cambiar<K extends keyof FiltrosBitacora>(campo: K, nuevo: FiltrosBitacora[K]) {
    setBorrador((actual) => ({ ...actual, [campo]: nuevo }))
  }

  function buscar(evento: FormEvent) {
    evento.preventDefault()
    if (rangoInvalido) return
    setAplicados(borrador)
    setPagina(1)
  }

  function limpiar() {
    setBorrador(FILTROS_BITACORA_VACIOS)
    setAplicados(FILTROS_BITACORA_VACIOS)
    setPagina(1)
  }

  const datos = consulta.data
  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / TAMANO_PAGINA_BITACORA)) : 1

  return (
    <>
      <section className="header-banner">
        <h1>Bitácora de cambios</h1>
        <p>Consulte quién, cuándo y qué cambió en el sistema.</p>
      </section>

      <form onSubmit={buscar} noValidate>
        <TableFilters
          hasActiveFilters={hayFiltros || hayFiltrosBitacora(borrador)}
          onClear={limpiar}
        >
          <div className="form-group">
            <label className="form-label" htmlFor="bitacora-desde">Desde</label>
            <input
              id="bitacora-desde"
              type="date"
              className="form-control"
              value={borrador.desde}
              aria-invalid={rangoInvalido || undefined}
              onChange={(evento) => cambiar('desde', evento.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bitacora-hasta">Hasta</label>
            <input
              id="bitacora-hasta"
              type="date"
              className="form-control"
              value={borrador.hasta}
              aria-invalid={rangoInvalido || undefined}
              onChange={(evento) => cambiar('hasta', evento.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bitacora-entidad">Entidad</label>
            <input
              id="bitacora-entidad"
              type="search"
              className="form-control"
              maxLength={LONGITUD_MAXIMA_ENTIDAD}
              value={borrador.entidad}
              onChange={(evento) => cambiar('entidad', evento.target.value)}
            />
          </div>
          <Select
            id="bitacora-rol"
            label="Rol"
            value={borrador.rol}
            opciones={[
              { value: '', label: 'Todos' },
              ...(Object.entries(ETIQUETAS_ROL) as [CodigoRol, string][]).map(
                ([value, label]) => ({ value, label }),
              ),
            ]}
            onChange={(evento) => cambiar('rol', evento.target.value as CodigoRol | '')}
          />
          <Select
            id="bitacora-accion"
            label="Acción"
            value={borrador.accion}
            opciones={[
              { value: '', label: 'Todas' },
              ...(Object.entries(ETIQUETAS_ACCION) as [AccionBitacora, string][]).map(
                ([value, label]) => ({ value, label }),
              ),
            ]}
            onChange={(evento) => cambiar('accion', evento.target.value as AccionBitacora | '')}
          />
          <div className="form-group">
            <label className="form-label" htmlFor="bitacora-registro">N.º de registro</label>
            <input
              id="bitacora-registro"
              type="number"
              min={1}
              inputMode="numeric"
              className="form-control"
              value={borrador.registro_id}
              onChange={(evento) => cambiar('registro_id', evento.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="bitacora-usuario">ID de usuario</label>
            <input
              id="bitacora-usuario"
              type="number"
              min={1}
              inputMode="numeric"
              className="form-control"
              value={borrador.usuario_id}
              onChange={(evento) => cambiar('usuario_id', evento.target.value)}
            />
          </div>
          <Select
            id="bitacora-orden"
            label="Orden"
            value={borrador.orden}
            opciones={[
              { value: 'desc', label: 'Más recientes primero' },
              { value: 'asc', label: 'Más antiguos primero' },
            ]}
            onChange={(evento) => cambiar('orden', evento.target.value as FiltrosBitacora['orden'])}
          />
          <div className="form-group table-filter-submit">
            <button className="btn btn-primary" type="submit" disabled={rangoInvalido}>Buscar</button>
          </div>
        </TableFilters>
        {rangoInvalido && (
          <p className="alert-error" role="alert">
            La fecha «Desde» no puede ser posterior a la fecha «Hasta».
          </p>
        )}
      </form>

      {consulta.isPending && <p className="estado-pagina" role="status">Cargando bitácora…</p>}
      {consulta.isError && (
        <section className="alert-error" role="alert">
          <p>
            {consulta.error instanceof ApiError
              ? consulta.error.message
              : 'No se pudo consultar la bitácora.'}
          </p>
          <button
            className="btn btn-outline btn-small"
            type="button"
            disabled={consulta.isFetching}
            onClick={() => { void consulta.refetch() }}
          >
            {consulta.isFetching ? 'Consultando…' : 'Reintentar'}
          </button>
        </section>
      )}

      {datos && !consulta.isError && (
        <section aria-busy={consulta.isFetching}>
          <ResultsCount count={datos.total} />
          <DataTable
            columns={COLUMNAS}
            rows={datos.items}
            rowKey={(fila) => fila.id}
            label="Bitácora de cambios"
            emptyMessage={
              hayFiltros
                ? 'No se encontraron registros con los filtros seleccionados.'
                : 'Aún no hay registros en la bitácora.'
            }
            onClearEmpty={hayFiltros ? limpiar : undefined}
          />
          {datos.total > 0 && (
            <nav className="table-filters-actions" aria-label="Paginación de la bitácora">
              <button
                type="button"
                className="btn btn-outline btn-small"
                disabled={pagina <= 1 || consulta.isFetching}
                onClick={() => setPagina((actual) => actual - 1)}
              >
                Anterior
              </button>
              <span>Página {pagina} de {totalPaginas}</span>
              <button
                type="button"
                className="btn btn-outline btn-small"
                disabled={pagina >= totalPaginas || consulta.isFetching}
                onClick={() => setPagina((actual) => actual + 1)}
              >
                Siguiente
              </button>
            </nav>
          )}
        </section>
      )}
    </>
  )
}

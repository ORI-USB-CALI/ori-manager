import { useState } from 'react'

import { AvisoNotificacion } from './notificaciones/AvisoNotificacion'
import {
  CATEGORIAS_AVISOS, contarAsuntosPendientes, unificarAvisos,
  type CategoriaAviso, type FuenteAvisos,
} from './notificaciones/avisos'

interface CentroNotificacionesProps {
  fuentes: FuenteAvisos[]
  onActualizar?: () => void
  actualizando?: boolean
}

export function CentroNotificaciones({ fuentes, onActualizar, actualizando }: CentroNotificacionesProps) {
  const [filtro, setFiltro] = useState<CategoriaAviso | 'todos'>('todos')
  const filtroActual = fuentes.some((fuente) => fuente.categoria === filtro) ? filtro : 'todos'
  const visibles = fuentes.filter((fuente) => filtroActual === 'todos' || fuente.categoria === filtroActual)
  const avisos = unificarAvisos(visibles.flatMap((fuente) => fuente.avisos))
  const pendientes = contarAsuntosPendientes(fuentes.flatMap((fuente) => fuente.avisos))
  const cargando = visibles.some((fuente) => fuente.cargando)
  const error = visibles.some((fuente) => fuente.error)

  return (
    <div className="centro-notificaciones">
      <p className="centro-notificaciones-resumen" role="status">
        {pendientes} {pendientes === 1 ? 'asunto pendiente' : 'asuntos pendientes'} de atención
      </p>
      <div className="centro-notificaciones-filtros" role="group" aria-label="Categorías de notificaciones">
        <button type="button" aria-pressed={filtroActual === 'todos'} onClick={() => setFiltro('todos')}>Todos</button>
        {fuentes.map(({ categoria }) => (
          <button key={categoria} type="button" aria-pressed={filtroActual === categoria}
            onClick={() => setFiltro(categoria)}>{CATEGORIAS_AVISOS[categoria].etiqueta}</button>
        ))}
      </div>
      {onActualizar && <button className="btn-link" type="button" disabled={actualizando} onClick={onActualizar}>
        {actualizando ? 'Actualizando…' : 'Actualizar avisos'}
      </button>}
      {cargando && <p className="bandeja-notificaciones-estado" role="status">Consultando notificaciones…</p>}
      {visibles.filter((fuente) => fuente.error).map(({ categoria }) => (
        <p key={categoria} className="bandeja-notificaciones-error" role="alert">{CATEGORIAS_AVISOS[categoria].error}</p>
      ))}
      {!cargando && !error && avisos.length === 0 && (
        <p className="bandeja-notificaciones-estado">
          {filtroActual === 'todos' ? 'No tienes notificaciones pendientes' : CATEGORIAS_AVISOS[filtroActual].vacio}
        </p>
      )}
      {avisos.length > 0 && (
        <ul className="centro-notificaciones-lista" aria-label="Notificaciones">
          {avisos.map((aviso) => <li key={aviso.id}><AvisoNotificacion aviso={aviso} /></li>)}
        </ul>
      )}
    </div>
  )
}

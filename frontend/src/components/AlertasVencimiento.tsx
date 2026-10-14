import { Link } from 'react-router-dom'

import type { AlertaVencimiento } from '../pages/alertasVencimiento'
import { adaptarVencimientos, formatearFechaAviso } from './notificaciones/avisos'

interface AlertasVencimientoProps {
  alertas: AlertaVencimiento[] | undefined
  cargando: boolean
  error: boolean
}

/** Resumen de Inicio; el listado completo pertenece al Centro de notificaciones. */
export function AlertasVencimiento({ alertas, cargando, error }: AlertasVencimientoProps) {
  const avisos = adaptarVencimientos(alertas).sort((a, b) =>
    (a.fecha?.valor ?? '').localeCompare(b.fecha?.valor ?? ''))

  return (
    <section className="card resumen-vencimientos" aria-labelledby="resumen-vencimientos-titulo">
      <header>
        <h2 id="resumen-vencimientos-titulo">Próximos vencimientos</h2>
        <p>Convenios que vencen dentro de los próximos 120 días y requieren una decisión de renovación.</p>
      </header>
      {cargando && <p role="status">Consultando vencimientos…</p>}
      {error && <p role="alert">No fue posible consultar los avisos de vencimiento.</p>}
      {!cargando && !error && avisos.length === 0 && <p>No tienes vencimientos pendientes</p>}
      {avisos.length > 0 && <>
        <p>{avisos.length} {avisos.length === 1 ? 'convenio próximo' : 'convenios próximos'} a vencer</p>
        <ul className="resumen-vencimientos-lista">
          {avisos.slice(0, 3).map((aviso) => (
            <li key={aviso.id}>
              <strong>{aviso.entidad.identificacion}</strong>
              <span className={`badge badge-${aviso.prioridad?.variante}`}>{aviso.prioridad?.etiqueta}</span>
              {aviso.fecha && <span>Vence: <time dateTime={aviso.fecha.valor}>{formatearFechaAviso(aviso.fecha)}</time></span>}
              <p>{aviso.descripcion}</p>
              <Link to={aviso.ruta}>{aviso.textoAccion}</Link>
            </li>
          ))}
        </ul>
      </>}
      <Link to="/renovaciones?estado=PENDIENTE_DE_DECISION">Ver gestión de renovaciones</Link>
    </section>
  )
}

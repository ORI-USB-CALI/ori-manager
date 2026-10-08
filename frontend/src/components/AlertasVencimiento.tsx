import { Link } from 'react-router-dom'

import {
  type AlertaVencimiento,
  type RangoVencimiento,
} from '../pages/alertasVencimiento'

interface ConfiguracionRango {
  urgencia: string
  variante: 'danger' | 'warning' | 'info' | 'neutral'
}

const CONFIGURACION_RANGOS: Record<RangoVencimiento, ConfiguracionRango> = {
  '0_30': { urgencia: 'Urgente', variante: 'danger' },
  '31_60': { urgencia: 'Prioritario', variante: 'warning' },
  '61_90': { urgencia: 'Atención', variante: 'info' },
  '91_120': { urgencia: 'Seguimiento', variante: 'neutral' },
}

function formatearFecha(fecha: string): string {
  return new Date(`${fecha}T00:00:00Z`).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function identificacion(alerta: AlertaVencimiento): string {
  return alerta.codigo?.trim() || alerta.objeto?.trim() || `Convenio #${alerta.convenio_id}`
}

function descripcion(alerta: AlertaVencimiento): string | null {
  const objeto = alerta.objeto?.trim()
  return alerta.codigo?.trim() && objeto ? objeto : null
}

function diasRestantes(dias: number): string {
  if (dias === 0) return '0 días restantes · vence hoy'
  return `${dias} ${dias === 1 ? 'día restante' : 'días restantes'}`
}

interface AlertasVencimientoProps {
  alertas: AlertaVencimiento[] | undefined
  cargando: boolean
  error: boolean
}

export function AlertasVencimiento({ alertas, cargando, error }: AlertasVencimientoProps) {
  return (
    <section className="avisos-vencimiento" aria-labelledby="avisos-vencimiento-titulo">
      <header className="avisos-vencimiento-cabecera">
        <h3 id="avisos-vencimiento-titulo">Vencimientos</h3>
        <p>Convenios que vencen dentro de los próximos 120 días y requieren una decisión de renovación.</p>
      </header>

      {cargando && (
        <p className="bandeja-notificaciones-estado">Consultando vencimientos…</p>
      )}

      {error && (
        <p className="bandeja-notificaciones-error" role="alert">
          No fue posible consultar los avisos de vencimiento.
        </p>
      )}

      {!cargando && !error && alertas?.length === 0 && (
        <p className="bandeja-notificaciones-estado">
          No hay avisos de vencimiento pendientes.
        </p>
      )}

      {alertas && alertas.length > 0 && (
        <ul className="avisos-vencimiento-lista" aria-label="Convenios próximos a vencer">
          {alertas.map((alerta) => {
            const rango = CONFIGURACION_RANGOS[alerta.rango_vencimiento]
            const detalle = descripcion(alerta)

            return (
              <li key={alerta.convenio_id}>
                <article
                  className={`aviso-vencimiento aviso-vencimiento-${rango.variante}`}
                >
                  <div className="aviso-vencimiento-nivel">
                    <span className={`badge badge-${rango.variante}`}>{rango.urgencia}</span>
                  </div>
                  <div className="aviso-vencimiento-identificacion">
                    <h4>{identificacion(alerta)}</h4>
                    {detalle && <p>{detalle}</p>}
                  </div>
                  <dl className="aviso-vencimiento-datos">
                    <div>
                      <dt>Vence</dt>
                      <dd>{formatearFecha(alerta.fecha_vencimiento)}</dd>
                    </div>
                    <div>
                      <dt>Vigencia restante</dt>
                      <dd>{diasRestantes(alerta.dias_restantes)}</dd>
                    </div>
                  </dl>
                  <Link
                    className="aviso-vencimiento-enlace"
                    to={`/renovaciones?estado=PENDIENTE_DE_DECISION&convenio_id=${alerta.convenio_id}`}
                  >
                    Gestionar renovación
                  </Link>
                </article>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

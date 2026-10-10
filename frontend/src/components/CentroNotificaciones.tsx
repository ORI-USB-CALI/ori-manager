import { Link } from 'react-router-dom'

import {
  type Notificacion,
  type TipoNotificacion,
  useMarcarNotificacionLeida,
} from '../pages/notificaciones'

interface ConfiguracionTipo {
  etiqueta: string
  variante: 'danger' | 'warning' | 'info'
}

const CONFIGURACION_TIPOS: Record<TipoNotificacion, ConfiguracionTipo> = {
  REVISION_JURIDICA_PENDIENTE: { etiqueta: 'Revisión jurídica', variante: 'info' },
  DEVOLUCION_REVISION: { etiqueta: 'Devolución', variante: 'warning' },
  SOLICITUD_DEVUELTA: { etiqueta: 'Solicitud devuelta', variante: 'warning' },
  REVISION_CONTRAPARTE_PENDIENTE: { etiqueta: 'Revisión de contraparte', variante: 'info' },
}

function enlaceDestino(notificacion: Notificacion): string {
  switch (notificacion.tipo) {
    case 'REVISION_JURIDICA_PENDIENTE':
    case 'DEVOLUCION_REVISION':
      // Destinatarios: Revisor ORI o el Gestor que creó el convenio, ambos
      // con permiso convenios.ver.
      return `/convenios/${notificacion.entidad_id}`
    case 'REVISION_CONTRAPARTE_PENDIENTE':
      // Destinatario: el Solicitante, que no tiene convenios.ver. Se envía
      // a su listado de revisiones de contraparte pendientes.
      return '/revisiones-contraparte'
    case 'SOLICITUD_DEVUELTA':
      return `/solicitudes/${notificacion.entidad_id}`
  }
}

function formatearFecha(fecha: string): string {
  return new Date(fecha).toLocaleString('es-CO', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface CentroNotificacionesProps {
  notificaciones: Notificacion[] | undefined
  cargando: boolean
  error: boolean
}

export function CentroNotificaciones({
  notificaciones,
  cargando,
  error,
}: CentroNotificacionesProps) {
  const marcarLeida = useMarcarNotificacionLeida()

  return (
    <section className="centro-notificaciones" aria-labelledby="centro-notificaciones-titulo">
      <header className="avisos-vencimiento-cabecera">
        <h3 id="centro-notificaciones-titulo">Notificaciones</h3>
        <p>Acciones pendientes que requieren su atención.</p>
      </header>

      {cargando && (
        <p className="bandeja-notificaciones-estado">Consultando notificaciones…</p>
      )}

      {error && (
        <p className="bandeja-notificaciones-error" role="alert">
          No fue posible consultar sus notificaciones.
        </p>
      )}

      {!cargando && !error && notificaciones?.length === 0 && (
        <p className="bandeja-notificaciones-estado">No tiene notificaciones.</p>
      )}

      {notificaciones && notificaciones.length > 0 && (
        <ul className="centro-notificaciones-lista" aria-label="Notificaciones">
          {notificaciones.map((notificacion) => {
            const configuracion = CONFIGURACION_TIPOS[notificacion.tipo]

            return (
              <li key={notificacion.id}>
                <article
                  className={`centro-notificacion centro-notificacion-${configuracion.variante}${
                    notificacion.leida ? '' : ' centro-notificacion-no-leida'
                  }`}
                >
                  <div className="centro-notificacion-nivel">
                    <span className={`badge badge-${configuracion.variante}`}>
                      {configuracion.etiqueta}
                    </span>
                    <time dateTime={notificacion.creado_en}>
                      {formatearFecha(notificacion.creado_en)}
                    </time>
                  </div>
                  <p className="centro-notificacion-mensaje">{notificacion.mensaje}</p>
                  <div className="centro-notificacion-acciones">
                    <Link
                      className="aviso-vencimiento-enlace"
                      to={enlaceDestino(notificacion)}
                      onClick={() => {
                        if (!notificacion.leida) marcarLeida.mutate(notificacion.id)
                      }}
                    >
                      Ver
                    </Link>
                    {!notificacion.leida && (
                      <button
                        type="button"
                        className="btn-link"
                        onClick={() => marcarLeida.mutate(notificacion.id)}
                        disabled={marcarLeida.isPending}
                      >
                        Marcar como leída
                      </button>
                    )}
                  </div>
                </article>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

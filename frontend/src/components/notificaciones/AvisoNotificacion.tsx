import { Link } from 'react-router-dom'

import { useMarcarNotificacionLeida } from '../../pages/notificaciones'
import { formatearFechaAviso, type Aviso } from './avisos'

export function AvisoNotificacion({ aviso }: { aviso: Aviso }) {
  const marcarLeida = useMarcarNotificacionLeida()
  const lectura = aviso.lectura
  const sinLeer = lectura && !lectura.leida
  const variante = aviso.prioridad?.variante ?? 'info'

  return (
    <article className={`centro-notificacion centro-notificacion-${variante}${sinLeer ? ' centro-notificacion-no-leida' : ''}${aviso.estadoAtencion === 'atendida' ? ' centro-notificacion-atendida' : ''}`}>
      <div className="centro-notificacion-nivel">
        <span className={`badge badge-${variante}`}>{aviso.titulo}</span>
        {aviso.prioridad && <span className={`badge badge-${variante}`}>{aviso.prioridad.etiqueta}</span>}
        <span className="badge badge-neutral">{aviso.estadoAtencion === 'atendida' ? 'Atendida' : 'Pendiente'}</span>
        {lectura && <span>{lectura.leida ? 'Leída' : 'No leída'}</span>}
      </div>
      <h4>{aviso.entidad.identificacion}</h4>
      <p className="centro-notificacion-mensaje">{aviso.descripcion}</p>
      {aviso.fecha && (
        <p className="centro-notificacion-fecha">
          {aviso.fecha.etiqueta}: <time dateTime={aviso.fecha.valor}>{formatearFechaAviso(aviso.fecha)}</time>
        </p>
      )}
      <div className="centro-notificacion-acciones">
        <Link className="aviso-vencimiento-enlace" to={aviso.ruta} onClick={() => {
          if (sinLeer) marcarLeida.mutate(lectura.notificacionId)
        }}>{aviso.textoAccion}</Link>
        {sinLeer && (
          <button type="button" className="btn-link" disabled={marcarLeida.isPending}
            onClick={() => marcarLeida.mutate(lectura.notificacionId)}>
            Marcar como leída
          </button>
        )}
      </div>
      {marcarLeida.isError && <p role="alert">No fue posible marcar la notificación como leída. Inténtalo de nuevo.</p>}
    </article>
  )
}

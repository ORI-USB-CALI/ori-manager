import { useSesion } from '../auth/sesion'
import {
  adaptarNotificacion, adaptarVencimientos, contarAsuntosPendientes,
  type FuenteAvisos, unificarAvisos,
} from '../components/notificaciones/avisos'
import { useAlertasVencimiento } from './alertasVencimiento'
import { useNotificaciones } from './notificaciones'

/** Compone fuentes autorizadas; cada servicio conserva su contrato y su caché. */
export function useCentroNotificaciones() {
  const { sesion, puede } = useSesion()
  const verVencimientos = Boolean(sesion) && puede('convenios.ver_alertas_vencimiento')
  const notificaciones = useNotificaciones(Boolean(sesion))
  const vencimientos = useAlertasVencimiento(verVencimientos)
  const fuentes: FuenteAvisos[] = [{
    categoria: 'acciones',
    avisos: (notificaciones.data ?? []).map(adaptarNotificacion),
    cargando: notificaciones.isPending,
    error: notificaciones.isError,
  }]
  if (verVencimientos) fuentes.push({
    categoria: 'vencimientos',
    avisos: adaptarVencimientos(vencimientos.data),
    cargando: vencimientos.isPending,
    error: vencimientos.isError,
  })
  const avisos = unificarAvisos(fuentes.flatMap((fuente) => fuente.avisos))

  return {
    fuentes,
    contador: contarAsuntosPendientes(avisos),
    actualizando: notificaciones.isFetching || (verVencimientos && vencimientos.isFetching),
    refrescar: () => {
      if (sesion) void notificaciones.refetch()
      if (verVencimientos) void vencimientos.refetch()
    },
  }
}

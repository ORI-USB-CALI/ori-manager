import type { AlertaVencimiento, RangoVencimiento } from '../../pages/alertasVencimiento'
import type { Notificacion, TipoNotificacion } from '../../pages/notificaciones'
import { referenciaConvenio } from '../../pages/epica02'

type Variante = 'danger' | 'warning' | 'info' | 'neutral'

interface AvisoBase {
  id: string
  titulo: string
  descripcion: string
  prioridad: { etiqueta: string; variante: Variante } | null
  entidad: { tipo: 'CONVENIO' | 'SOLICITUD'; id: number; identificacion: string }
  fecha?: { valor: string; etiqueta: string; formato: 'fecha' | 'instante' }
  estadoAtencion: 'pendiente' | 'atendida'
  ruta: string
  textoAccion: string
}

export type Aviso =
  | (AvisoBase & {
      categoria: 'acciones'
      tipo: TipoNotificacion
      lectura: { notificacionId: number; leida: boolean }
    })
  | (AvisoBase & { categoria: 'vencimientos'; tipo: RangoVencimiento; lectura?: never })

export type CategoriaAviso = Aviso['categoria']

export const CATEGORIAS_AVISOS: Record<CategoriaAviso, {
  etiqueta: string
  vacio: string
  error: string
}> = {
  acciones: {
    etiqueta: 'Acciones pendientes',
    vacio: 'No tienes acciones pendientes',
    error: 'No fue posible consultar sus notificaciones.',
  },
  vencimientos: {
    etiqueta: 'Vencimientos',
    vacio: 'No tienes vencimientos pendientes',
    error: 'No fue posible consultar los avisos de vencimiento.',
  },
}

const TIPOS_ACCION: Record<TipoNotificacion, { titulo: string; ruta: (id: number) => string }> = {
  REVISION_JURIDICA_PENDIENTE: { titulo: 'Revisión jurídica', ruta: (id) => `/convenios/${id}` },
  DEVOLUCION_REVISION: { titulo: 'Devolución', ruta: (id) => `/convenios/${id}` },
  SOLICITUD_DEVUELTA: { titulo: 'Solicitud devuelta', ruta: (id) => `/solicitudes/${id}` },
  REVISION_CONTRAPARTE_PENDIENTE: {
    titulo: 'Revisión de contraparte', ruta: () => '/revisiones-contraparte',
  },
}

const PRIORIDADES: Record<RangoVencimiento, NonNullable<Aviso['prioridad']>> = {
  '0_30': { etiqueta: 'Urgente', variante: 'danger' },
  '31_60': { etiqueta: 'Prioritario', variante: 'warning' },
  '61_90': { etiqueta: 'Atención', variante: 'info' },
  '91_120': { etiqueta: 'Seguimiento', variante: 'neutral' },
}

export function adaptarNotificacion(notificacion: Notificacion): Aviso {
  const tipo = TIPOS_ACCION[notificacion.tipo]
  return {
    id: `accion:${notificacion.id}`,
    categoria: 'acciones',
    tipo: notificacion.tipo,
    titulo: tipo.titulo,
    descripcion: notificacion.mensaje,
    prioridad: null,
    entidad: {
      tipo: notificacion.entidad_tipo,
      id: notificacion.entidad_id,
      identificacion: `${notificacion.entidad_tipo === 'CONVENIO' ? 'Convenio' : 'Solicitud'} #${notificacion.entidad_id}`,
    },
    fecha: { valor: notificacion.creado_en, etiqueta: 'Recibida', formato: 'instante' },
    estadoAtencion: notificacion.resuelta ? 'atendida' : 'pendiente',
    lectura: { notificacionId: notificacion.id, leida: notificacion.leida },
    ruta: tipo.ruta(notificacion.entidad_id),
    textoAccion: 'Ver',
  }
}

export function adaptarVencimiento(alerta: AlertaVencimiento): Aviso {
  const dias = alerta.dias_restantes
  const restante = dias === 0 ? '0 días restantes · vence hoy' : `${dias} ${dias === 1 ? 'día restante' : 'días restantes'}`
  return {
    id: `vencimiento:${alerta.convenio_id}`,
    categoria: 'vencimientos',
    tipo: alerta.rango_vencimiento,
    titulo: 'Vencimiento de convenio',
    descripcion: [alerta.objeto?.trim(), restante].filter(Boolean).join(' · '),
    prioridad: PRIORIDADES[alerta.rango_vencimiento],
    entidad: {
      tipo: 'CONVENIO',
      id: alerta.convenio_id,
      identificacion: alerta.codigo?.trim() || alerta.objeto?.trim() || referenciaConvenio(null, alerta.convenio_id),
    },
    fecha: { valor: alerta.fecha_vencimiento, etiqueta: 'Vence', formato: 'fecha' },
    estadoAtencion: 'pendiente',
    ruta: `/renovaciones?estado=PENDIENTE_DE_DECISION&convenio_id=${alerta.convenio_id}`,
    textoAccion: 'Gestionar renovación',
  }
}

/** Defensa de agregación: el backend sigue siendo la fuente de las reglas de negocio. */
export function adaptarVencimientos(alertas: AlertaVencimiento[] | undefined): Aviso[] {
  return unificarAvisos((alertas ?? [])
    .filter(({ dias_restantes }) => dias_restantes >= 0 && dias_restantes <= 120)
    .map(adaptarVencimiento))
}

export function unificarAvisos(avisos: Aviso[]): Aviso[] {
  return [...new Map(avisos.map((aviso) => [aviso.id, aviso])).values()]
}

export function contarAsuntosPendientes(avisos: Aviso[]): number {
  return unificarAvisos(avisos).filter((aviso) => aviso.estadoAtencion === 'pendiente').length
}

export interface FuenteAvisos {
  categoria: CategoriaAviso
  avisos: Aviso[]
  cargando: boolean
  error: boolean
}

export function formatearFechaAviso(fecha: NonNullable<Aviso['fecha']>): string {
  return fecha.formato === 'fecha'
    ? new Date(`${fecha.valor}T00:00:00Z`).toLocaleDateString('es-CO', {
        day: '2-digit', month: 'long', year: 'numeric', timeZone: 'UTC',
      })
    : new Date(fecha.valor).toLocaleString('es-CO', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      })
}

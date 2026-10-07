const LABELS: Record<string, string> = {
  BORRADOR: 'Borrador',
  RADICADA: 'Radicada',
  EN_ESTUDIO: 'En estudio',
  DEVUELTA: 'Devuelta',
  APROBADA: 'Aprobada',
  RECHAZADA: 'Rechazada',
  EN_TRAMITE: 'En trámite',
  VIGENTE: 'Vigente',
  POR_VENCER: 'Por vencer',
  VENCIDO: 'Vencido',
  RENOVADO: 'Renovado',
  FINALIZADO: 'Finalizado',
  CANCELADO: 'Cancelado',
  SOLICITUD: 'Solicitud',
  ELABORACION: 'Elaboración',
  REVISION_AVAL_JURIDICO: 'Revisión y aval jurídico',
  REVISION_CONTRAPARTE: 'Revisión de contraparte',
  REVISION_FINAL: 'Revisión final',
  APROBACION_FIRMAS: 'Aprobación y proceso de firmas',
  FIRMA_ARCHIVO_SEGUIMIENTO: 'Firma, archivo y seguimiento',
  INTERNO: 'Interno',
  EXTERNO: 'Externo',
}

const SUCCESS_VALUES = new Set(['APROBADA', 'VIGENTE', 'RENOVADO', 'ACTIVO'])
const WARNING_VALUES = new Set([
  'RADICADA',
  'EN_ESTUDIO',
  'DEVUELTA',
  'EN_TRAMITE',
  'POR_VENCER',
  'ELABORACION',
])
const DANGER_VALUES = new Set(['RECHAZADA', 'VENCIDO', 'CANCELADO', 'INACTIVO'])
const NEUTRAL_VALUES = new Set(['BORRADOR', 'FINALIZADO'])

export function enumLabel(value: string): string {
  return (
    LABELS[value] ??
    value
      .replaceAll('_', ' ')
      .toLocaleLowerCase('es')
      .replace(/^./, (letter) => letter.toLocaleUpperCase('es'))
  )
}

export function badgeVariant(value: string): string {
  if (SUCCESS_VALUES.has(value)) return 'badge-success'
  if (WARNING_VALUES.has(value)) return 'badge-warning'
  if (DANGER_VALUES.has(value)) return 'badge-danger'
  if (NEUTRAL_VALUES.has(value)) return 'badge-neutral'
  return 'badge-info'
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-CO', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

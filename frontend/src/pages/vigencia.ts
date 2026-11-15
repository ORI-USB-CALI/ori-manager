// HT-08/HT-17: mismas reglas que backend/services/vigencia.py. El backend decide; esto
// solo evita enviar fechas que ya sabemos inválidas y muestra el error por campo.
// Las fechas viajan como 'YYYY-MM-DD', así que se comparan como texto.

export const MENSAJE_VENCIMIENTO_PASADO = 'La fecha de vencimiento no puede ser anterior a hoy.'
export const MENSAJE_INICIO_POSTERIOR = 'La fecha de vencimiento debe ser igual o posterior a la fecha de inicio.'
export const MENSAJE_DURACION_INCOHERENTE = 'La fecha de vencimiento no coincide con la fecha de inicio y la duración: se suman los meses y se resta un día; si inicia a fin de mes conserva fin de mes.'

// Motivos que devuelve el backend en `faltantes` para `fecha_vencimiento`.
const MENSAJES_SERVIDOR: Record<string, string> = {
  'No puede ser anterior a la fecha actual': MENSAJE_VENCIMIENTO_PASADO,
  'Debe ser igual o posterior a la fecha de inicio': MENSAJE_INICIO_POSTERIOR,
  'No coincide con la fecha de inicio y la duración en meses': MENSAJE_DURACION_INCOHERENTE,
}

/** Día calendario del dominio ORI en America/Bogota, independiente del navegador. */
export function fechaHoyLocal(ahora: Date = new Date()): string {
  const partes = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(ahora)
  const valores = Object.fromEntries(partes.map((parte) => [parte.type, parte.value]))
  return `${valores.year}-${valores.month}-${valores.day}`
}

function dosDigitos(valor: number): string {
  return String(valor).padStart(2, '0')
}

/**
 * HT-17: suma meses calendario a una fecha 'YYYY-MM-DD'. Si el día no existe en
 * el mes de llegada se usa el último día de ese mes (31/01 + 1 mes = 28/02 o 29/02).
 * Se calcula con enteros y UTC para no depender de la zona del navegador.
 */
export function sumarMeses(fecha: string, meses: number): string {
  const [anioBase, mesBase, dia] = fecha.split('-').map(Number)
  const indice = mesBase - 1 + meses
  const anio = anioBase + Math.floor(indice / 12)
  const mes = (indice % 12) + 1
  const ultimoDia = new Date(Date.UTC(anio, mes, 0)).getUTCDate()
  return `${anio}-${dosDigitos(mes)}-${dosDigitos(Math.min(dia, ultimoDia))}`
}

/** Extremos inclusivos, conservando fin de mes cuando el inicio lo es. */
export function vencimientoEsperado(fechaInicio: string, duracionMeses: number): string {
  const destino = sumarMeses(fechaInicio, duracionMeses)
  const [anio, mes, dia] = fechaInicio.split('-').map(Number)
  const [a, m, d] = destino.split('-').map(Number)
  if (!Number.isInteger(duracionMeses) || a < 1 || a > 9999) return ''
  const finMes = dia === new Date(Date.UTC(anio, mes, 0)).getUTCDate()
  const resultado = finMes ? new Date(Date.UTC(a, m, 0)) : new Date(Date.UTC(a, m - 1, d - 1))
  return Number.isNaN(resultado.getTime()) ? '' : resultado.toISOString().slice(0, 10)
}

function formatoDia(fecha: string): string {
  const [anio, mes, dia] = fecha.split('-')
  return `${dia}/${mes}/${anio}`
}

/**
 * Solo valida lo informado: las fechas de vigencia y la duración son opcionales.
 * HT-17: si vienen inicio, vencimiento y una duración positiva, deben cuadrar.
 */
export function validarVigencia(
  fechaInicio: string | null,
  fechaVencimiento: string | null,
  hoy: string,
  duracionMeses: number | null = null,
): Record<string, string> {
  if (duracionMeses !== null && (!Number.isInteger(duracionMeses) || duracionMeses < 4)) return { duracion_meses: 'La duraci\u00f3n m\u00ednima es de 4 meses.' }
  if (fechaInicio && fechaInicio < hoy) return { fecha_inicio: 'La fecha de inicio no puede ser anterior a hoy.' }
  if (fechaInicio && duracionMeses !== null && !vencimientoEsperado(fechaInicio, duracionMeses)) return { duracion_meses: 'La duracion excede el rango de fechas permitido.' }
  if (!fechaVencimiento) return {}
  // CA-01: vencer hoy es válido.
  if (fechaVencimiento < hoy) return { fecha_vencimiento: MENSAJE_VENCIMIENTO_PASADO }
  if (!fechaInicio) return {}
  // CA-02/CA-03: inicio igual al vencimiento es válido.
  if (fechaInicio > fechaVencimiento) return { fecha_vencimiento: MENSAJE_INICIO_POSTERIOR }
  if (duracionMeses && Number.isInteger(duracionMeses) && duracionMeses > 0) {
    const esperado = vencimientoEsperado(fechaInicio, duracionMeses)
    // Una duración que sale del rango de años válido nunca puede cuadrar.
    if (esperado.length !== 10) return { fecha_vencimiento: MENSAJE_DURACION_INCOHERENTE }
    if (fechaVencimiento !== esperado) {
      return { fecha_vencimiento: `${MENSAJE_DURACION_INCOHERENTE} Para esa duración corresponde el ${formatoDia(esperado)}.` }
    }
  }
  return {}
}

export function mensajeVigenciaServidor(motivo: string): string | undefined {
  return MENSAJES_SERVIDOR[motivo]
}

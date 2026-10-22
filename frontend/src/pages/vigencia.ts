// HT-08: mismas reglas que backend/services/vigencia.py. El backend decide; esto
// solo evita enviar fechas que ya sabemos inválidas y muestra el error por campo.
// Las fechas viajan como 'YYYY-MM-DD', así que se comparan como texto.

export const MENSAJE_VENCIMIENTO_PASADO = 'La fecha de vencimiento no puede ser anterior a hoy.'
export const MENSAJE_INICIO_POSTERIOR = 'La fecha de vencimiento debe ser igual o posterior a la fecha de inicio.'

// Motivos que devuelve el backend en `faltantes` para `fecha_vencimiento`.
const MENSAJES_SERVIDOR: Record<string, string> = {
  'No puede ser anterior a la fecha actual': MENSAJE_VENCIMIENTO_PASADO,
  'Debe ser igual o posterior a la fecha de inicio': MENSAJE_INICIO_POSTERIOR,
}

/** Fecha local del navegador; cerca de medianoche puede diferir de Bogotá. */
export function fechaHoyLocal(ahora: Date = new Date()): string {
  const mes = String(ahora.getMonth() + 1).padStart(2, '0')
  const dia = String(ahora.getDate()).padStart(2, '0')
  return `${ahora.getFullYear()}-${mes}-${dia}`
}

/** Solo valida lo informado: las fechas de vigencia son opcionales. */
export function validarVigencia(
  fechaInicio: string | null,
  fechaVencimiento: string | null,
  hoy: string,
): Record<string, string> {
  if (!fechaVencimiento) return {}
  // CA-01: vencer hoy es válido.
  if (fechaVencimiento < hoy) return { fecha_vencimiento: MENSAJE_VENCIMIENTO_PASADO }
  // CA-02/CA-03: inicio igual al vencimiento es válido.
  if (fechaInicio && fechaInicio > fechaVencimiento) {
    return { fecha_vencimiento: MENSAJE_INICIO_POSTERIOR }
  }
  return {}
}

export function mensajeVigenciaServidor(motivo: string): string | undefined {
  return MENSAJES_SERVIDOR[motivo]
}

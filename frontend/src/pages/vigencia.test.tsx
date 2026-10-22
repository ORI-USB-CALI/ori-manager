import { describe, expect, it } from 'vitest'

import {
  MENSAJE_INICIO_POSTERIOR,
  MENSAJE_VENCIMIENTO_PASADO,
  fechaHoyLocal,
  mensajeVigenciaServidor,
  validarVigencia,
} from './vigencia'

const HOY = '2030-06-15'

describe('HT-08 - validación de vigencia en formularios', () => {
  it.each([
    ['sin fechas', null, null],
    ['solo inicio pasado', '2030-06-14', null],
    ['vence hoy', null, HOY],
    ['inicio igual al vencimiento', HOY, HOY],
    ['inicio pasado y vigente', '2030-06-14', '2030-06-16'],
  ])('CA-03: acepta %s', (_, inicio, vencimiento) => {
    expect(validarVigencia(inicio, vencimiento, HOY)).toEqual({})
  })

  it('CA-01: rechaza un vencimiento de ayer', () => {
    expect(validarVigencia(null, '2030-06-14', HOY)).toEqual({ fecha_vencimiento: MENSAJE_VENCIMIENTO_PASADO })
  })

  it('CA-02: rechaza un inicio posterior al vencimiento', () => {
    expect(validarVigencia('2030-06-17', '2030-06-16', HOY)).toEqual({ fecha_vencimiento: MENSAJE_INICIO_POSTERIOR })
  })

  it('traduce los motivos del backend y deja pasar los desconocidos', () => {
    expect(mensajeVigenciaServidor('No puede ser anterior a la fecha actual')).toBe(MENSAJE_VENCIMIENTO_PASADO)
    expect(mensajeVigenciaServidor('Debe ser igual o posterior a la fecha de inicio')).toBe(MENSAJE_INICIO_POSTERIOR)
    expect(mensajeVigenciaServidor('Otro motivo')).toBeUndefined()
  })

  it('usa la fecha local con formato YYYY-MM-DD', () => {
    expect(fechaHoyLocal(new Date(2030, 0, 5, 23, 59))).toBe('2030-01-05')
  })
})

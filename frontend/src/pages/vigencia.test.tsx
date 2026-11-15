import { describe, expect, it } from 'vitest'

import {
  MENSAJE_DURACION_INCOHERENTE,
  MENSAJE_INICIO_POSTERIOR,
  MENSAJE_VENCIMIENTO_PASADO,
  fechaHoyLocal,
  mensajeVigenciaServidor,
  sumarMeses,
  validarVigencia,
  vencimientoEsperado,
} from './vigencia'

const HOY = '2030-06-15'

describe('HT-08 - validación de vigencia en formularios', () => {
  it.each([
    ['sin fechas', null, null],
    ['vence hoy', null, HOY],
    ['inicio igual al vencimiento', HOY, HOY],
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

  it('usa el día calendario de Bogotá, independientemente del navegador', () => {
    // UTC 04:59 del día 6 aún corresponde a las 23:59 del día 5 en Bogotá.
    expect(fechaHoyLocal(new Date('2030-01-06T04:59:00.000Z'))).toBe('2030-01-05')
    // UTC 05:01 del día 6 corresponde a las 00:01 del día 6 en Bogotá.
    expect(fechaHoyLocal(new Date('2030-01-06T05:01:00.000Z'))).toBe('2030-01-06')
  })
})

describe('HT-17 - coherencia entre duración y fechas de vigencia', () => {
  it.each([
    ['31 de enero + 1 mes en año no bisiesto', '2031-01-31', 1, '2031-02-28'],
    ['31 de enero + 1 mes en año bisiesto', '2032-01-31', 1, '2032-02-29'],
    ['29 de febrero + 12 meses', '2032-02-29', 12, '2033-02-28'],
    ['cambio de año', '2031-11-15', 3, '2032-02-15'],
    ['31 de marzo + 1 mes', '2031-03-31', 1, '2031-04-30'],
  ])('suma meses: %s', (_, fecha, meses, esperado) => {
    expect(sumarMeses(fecha, meses)).toBe(esperado)
  })

  it.each([
    ['ejemplo de la regla (12 meses desde el 1 de enero)', '2031-01-01', 12, '2031-12-31'],
    ['fin de mes (31 de enero, 1 mes)', '2031-01-31', 1, '2031-02-28'],
    ['29 de febrero, 12 meses', '2032-02-29', 12, '2033-02-28'],
    ['cambio de año (15 de noviembre, 3 meses)', '2031-11-15', 3, '2032-02-14'],
    ['diciembre a enero', '2031-12-01', 1, '2031-12-31'],
  ])('vencimiento el mismo día del mes: %s', (_, inicio, meses, esperado) => {
    expect(vencimientoEsperado(inicio, meses)).toBe(esperado)
  })

  it('acepta un periodo coherente', () => {
    expect(validarVigencia('2031-01-01', '2031-12-31', HOY, 12)).toEqual({})
  })

  it('rechaza un periodo incoherente sobre fecha_vencimiento e indica el día esperado', () => {
    const errores = validarVigencia('2031-01-01', '2032-01-01', HOY, 12)
    expect(errores.fecha_vencimiento).toContain(MENSAJE_DURACION_INCOHERENTE)
    expect(errores.fecha_vencimiento).toContain('31/12/2031')
  })

  it.each([
    ['sin duración', '2031-01-01', '2032-01-01', null],
    ['sin inicio', null, '2032-01-01', 12],
    ['sin vencimiento', '2031-01-01', null, 12],
  ])('no valida la coherencia %s', (_, inicio, vencimiento, duracion) => {
    expect(validarVigencia(inicio, vencimiento, HOY, duracion)).toEqual({})
  })

  it('rechaza una nueva duracion inferior a cuatro meses', () => {
    expect(validarVigencia('2030-06-01', '2030-07-01', HOY, 1)).toHaveProperty('duracion_meses')
  })

  it('permite registrar un inicio hoy', () => {
    expect(validarVigencia(HOY, null, HOY, 4)).toEqual({})
  })

  it('prioriza el inicio posterior sobre la incoherencia', () => {
    expect(validarVigencia('2031-02-01', '2031-01-01', HOY, 12)).toEqual({ fecha_vencimiento: MENSAJE_INICIO_POSTERIOR })
  })

  it('una duración fuera de rango se reporta como incoherente', () => {
    expect(validarVigencia('2031-01-01', '2031-12-31', HOY, 10_000_000)).toHaveProperty('duracion_meses')
  })

  it('traduce el motivo del backend', () => {
    expect(mensajeVigenciaServidor('No coincide con la fecha de inicio y la duración en meses')).toBe(MENSAJE_DURACION_INCOHERENTE)
  })
})

 it.each([
 ['2027-01-01', 12, '2027-12-31'],
 ['2027-01-15', 4, '2027-05-14'],
 ['2027-01-31', 4, '2027-05-31'],
 ['2026-10-31', 4, '2027-02-28'],
 ['2028-02-29', 12, '2029-02-28'],
 ])('HT17 cierre %s', (inicio, meses, esperado) => {
 expect(vencimientoEsperado(inicio as string, meses as number)).toBe(esperado)
 })

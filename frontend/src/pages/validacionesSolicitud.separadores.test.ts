import { describe, expect, it } from 'vitest'

import type { TipoIdentificacion } from './epica02'
import { validarDigitoVerificacionNit, validarIdentificacion, validarTelefono } from './validacionesSolicitud'

const PROHIBIDOS = ['\u0085', '\u001c', '\ufeff', '\u200b', '\u202e', '\t']
const ESPACIOS = ' \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000'
const CASOS: [TipoIdentificacion, string, string][] = [
  ['NIT', '900', '123456'], ['CEDULA_CIUDADANIA', '1144', '123456'],
  ['CEDULA_EXTRANJERIA', 'ab', '123'], ['PASAPORTE', 'ab', '12345'],
  ['IDENTIFICACION_FISCAL_EXTRANJERA', 'RFC', 'AB1'], ['OTRO', 'Registro', '123'],
]

describe('H-07: separadores explícitos compartidos con backend', () => {
  for (const posicion of ['inicio', 'interior', 'final'] as const) {
    for (const control of PROHIBIDOS) {
      it.each(CASOS)(`rechaza control U+${control.codePointAt(0)?.toString(16)} al ${posicion} de %s`, (tipo, izquierda, derecha) => {
        const valor = { inicio: control + izquierda + derecha, interior: izquierda + control + derecha, final: izquierda + derecha + control }[posicion]
        expect(validarIdentificacion(tipo, valor)).not.toBeNull()
      })
    }
  }

  it.each(CASOS)('admite los espacios horizontales legítimos de %s', (tipo, izquierda, derecha) => {
    for (const espacio of ESPACIOS) {
      expect(validarIdentificacion(tipo, espacio + izquierda + espacio + derecha + espacio)).toBeNull()
    }
    expect(validarIdentificacion('NIT', '900.123.456')).toBeNull()
    expect(validarIdentificacion('CEDULA_CIUDADANIA', '1.144 123.456')).toBeNull()
  })

  for (const control of PROHIBIDOS) {
    it.each(['{c}8', '8{c}', '{c}8{c}'])(`DV rechaza U+${control.codePointAt(0)?.toString(16)} en %s`, (patron) => {
      expect(validarDigitoVerificacionNit('900123456', patron.replaceAll('{c}', control))).not.toBeNull()
    })
    it.each(['{c}3001234567', '300{c}1234567', '3001234567{c}'])(`teléfono rechaza U+${control.codePointAt(0)?.toString(16)} en %s`, (patron) => {
      expect(validarTelefono(patron.replaceAll('{c}', control))).not.toBeNull()
    })
  }

  it('DV admite espacios legítimos en bordes, sin admitir dos dígitos', () => {
    for (const espacio of ESPACIOS) expect(validarDigitoVerificacionNit('900123456', espacio + '8' + espacio)).toBeNull()
    expect(validarDigitoVerificacionNit(null, '8 8')).not.toBeNull()
  })

  it('teléfono conserva espacios legítimos y extensiones', () => {
    for (const espacio of ESPACIOS) {
      expect(validarTelefono(espacio + '+57' + espacio + '6025551234' + espacio + 'ext' + espacio + '000123' + espacio)).toBeNull()
    }
    expect(validarTelefono('+576025551234;ext=000123')).toBeNull()
  })

  it.each(CASOS)('no acepta un terminador final en %s', (tipo, izquierda, derecha) => {
    for (const terminador of ['\n', '\r', '\u2028', '\u2029']) {
      expect(validarIdentificacion(tipo, izquierda + derecha + terminador)).not.toBeNull()
    }
  })

  it('DV y teléfono tampoco aceptan terminadores finales', () => {
    for (const terminador of ['\n', '\r', '\u2028', '\u2029']) {
      expect(validarDigitoVerificacionNit('900123456', '8' + terminador)).not.toBeNull()
      expect(validarTelefono('3001234567' + terminador)).not.toBeNull()
    }
  })
})

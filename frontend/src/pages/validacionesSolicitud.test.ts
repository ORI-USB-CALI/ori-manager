import { describe, expect, it } from 'vitest'

import {
  calcularDigitoVerificacionNit,
  validarCiudad,
  validarDigitoVerificacionNit,
  validarDireccion,
  validarIdentificacion,
  validarTelefono,
} from './validacionesSolicitud'

/** HT14-FE02: mismos casos que backend/tests/test_ht14_validaciones.py (RN-02). */
describe('validaciones de formato de la solicitud', () => {
  it.each(['Cali', 'Bogotá', 'Medellín', 'São Paulo', 'München', 'Saint-Denis', "L'Aquila", 'St. Louis', 'Ñuñoa'])(
    'acepta la ciudad %s', (ciudad) => expect(validarCiudad(ciudad)).toBeNull(),
  )

  it.each(['C', 'Cali 123', '123', '-Cali', 'Cali@', 'x'.repeat(121)])(
    'rechaza la ciudad %s', (ciudad) => expect(validarCiudad(ciudad)).toContain('La ciudad debe tener'),
  )

  it.each(['Calle 5 # 10-20', 'Carrera 100 # 11-90 Of. 301', 'Vereda El Peñón km 3', 'Avenida Córdoba 123', 'Rua Augusta, 1500', '1600 Pennsylvania Ave NW'])(
    'acepta la dirección %s', (direccion) => expect(validarDireccion(direccion)).toBeNull(),
  )

  it.each(['Cra', '12345', 'Calle 5 @ 10', 'Calle_5 10', 'x'.repeat(201)])(
    'rechaza la dirección %s', (direccion) => expect(validarDireccion(direccion)).toContain('La dirección debe tener'),
  )

  it.each(['3001234567', '+57 300 123 4567', '(602) 555-1234', '+34 912 345 678', '6025551234 ext 12', '602 555 1234 ext. 123', '6025551234 x12', '6025551234 extensión 7'])(
    'acepta el teléfono %s', (telefono) => expect(validarTelefono(telefono)).toBeNull(),
  )

  it.each(['abc', '300-CALL-NOW', '123', '6025551234 ext', '6025551234 ext 1234567'])(
    'rechaza el teléfono %s', (telefono) => expect(validarTelefono(telefono)).toContain('Ingrese un teléfono válido'),
  )

  it.each([
    ['NIT', '900.123.456'],
    ['CEDULA_CIUDADANIA', '1.144.000.111'],
    ['CEDULA_EXTRANJERIA', 'ab 123'],
    ['PASAPORTE', 'ab12345'],
    ['OTRO', 'REG-123/45'],
  ] as const)('acepta %s con el valor %s', (tipo, valor) => expect(validarIdentificacion(tipo, valor)).toBeNull())

  it.each([
    ['NIT', '900123456-8'],
    ['NIT', '1234'],
    ['CEDULA_CIUDADANIA', 'ABC123'],
    ['CEDULA_EXTRANJERIA', 'A1'],
    ['PASAPORTE', 'A123'],
    ['OTRO', 'A'],
  ] as const)('rechaza %s con el valor %s', (tipo, valor) => expect(validarIdentificacion(tipo, valor)).not.toBeNull())

  it('comprueba el dígito de verificación del NIT', () => {
    expect(calcularDigitoVerificacionNit('900123456')).toBe(8)
    expect(validarDigitoVerificacionNit('900123456', '8')).toBeNull()
    expect(validarDigitoVerificacionNit('900123456', '0')).toContain('no es correcto')
    expect(validarDigitoVerificacionNit('900123456', '88')).toContain('un solo dígito')
  })
})

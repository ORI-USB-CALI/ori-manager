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

  it.each(['+576025551234;ext=1', '+576025551234;ext=123456', '+576025551234;ext=000001', '+576025551234', '+44 (20) 7946-0958'])('H-01: admite el teléfono canónico o humano %s', (valor) => {
    expect(validarTelefono(valor)).toBeNull()
  })

  it.each(['+576025551234;ext=', '+576025551234;ext=1234567', '+576025551234;ext=abc', '+576025551234;foo=1', '6025551234;ext=1'])('H-01: rechaza sintaxis de extensión arbitraria %s', (valor) => {
    expect(validarTelefono(valor)).not.toBeNull()
  })

  it.each(['Calle 5 # 38-25', 'Cra. 122 No. 6-65, Pance', 'Vereda La Esperanza, Finca El Roble', 'Km 3 vía Cali/Jamundí', '1600 Amphitheatre Pkwy', 'Apartado postal 123', 'Edificio Central, oficina 402', 'Finca El Roble, zona rural de Pance', 'The Old Rectory, High Street', 'Campus universitario, Pance', '東京都渋谷区神南1丁目', 'Maison du Lac / Les Pins'])('H-02: admite la dirección %s', (valor) => {
    expect(validarDireccion(valor)).toBeNull()
  })

  it.each(['Hola como estas', 'Texto sin referencia', 'AAAAA', ' , Casa', 'Casa, ', '#-.,/'])('H-02: rechaza texto sin estructura %s', (valor) => {
    expect(validarDireccion(valor)).not.toBeNull()
  })

  it('valida el DV parcial y rechaza identificaciones solo de signos', () => {
    expect(validarDigitoVerificacionNit(null, '8')).toBeNull()
    expect(validarDigitoVerificacionNit(null, 'A')).not.toBeNull()
    expect(validarDigitoVerificacionNit('900123456', '٨')).not.toBeNull()
    expect(validarIdentificacion('OTRO', '---/.')).not.toBeNull()
    expect(validarIdentificacion('IDENTIFICACION_FISCAL_EXTRANJERA', '---/.')).not.toBeNull()
  })

  it('admite texto Unicode normalizado y longitudes por caracteres', () => {
    expect(validarCiudad('Bogota\u0301')).toBeNull()
    expect(validarDireccion('Edificio Pen\u0303a, oficina 2')).toBeNull()
    expect(validarCiudad('𐐀'.repeat(120))).toBeNull()
    expect(validarDireccion('𐐀'.repeat(199) + '1')).toBeNull()
  })
})

describe('H-06: Unicode y longitud del texto canónico', () => {
  it.each([
    'A'.repeat(59) + ' '.repeat(50) + 'B'.repeat(60),
    'e\u0301'.repeat(120), 'Qq\u0323', 'मुंबई', 'q\u0323'.repeat(60),
    '\t São\u00a0\u00a0Paulo\r\n',
  ])('admite ciudad normalizable o con marcas de letras: %s', (valor) => {
    expect(validarCiudad(valor)).toBeNull()
  })

  it.each([
    'A'.repeat(99) + ' '.repeat(80) + 'B'.repeat(98) + ' 1',
    'e\u0301'.repeat(199) + '1', 'Finca Qq\u0323, Pance', 'मुंबई 12',
    'q\u0323'.repeat(99) + 'a1',
  ])('admite dirección normalizable o con marcas de letras: %s', (valor) => {
    expect(validarDireccion(valor)).toBeNull()
  })

  it.each([
    '\u0323Cali', 'Ca \u0323li', 'Ca-\u0323li', 'Ca\x00li', 'Ca\x1cli',
    'Ca\u0085li', 'Ca\u200bli', 'Ca\u202eli', '\ufeffCali', 'Cali@',
    'q\u0323'.repeat(60) + 'a', 'e\u0301'.repeat(121),
  ])('rechaza ciudad con marcas huérfanas, controles o exceso: %s', (valor) => {
    expect(validarCiudad(valor)).not.toBeNull()
  })

  it.each([
    'Casa \u0323, Pance', 'Calle 1\u0323', 'Casa\x001', 'Casa\x1c1',
    'Casa\u00851', 'Casa\u200b1', '\ufeffCasa 1', 'Casa <b>1</b>',
    'q\u0323'.repeat(99) + 'aa1', 'e\u0301'.repeat(200) + '1',
  ])('rechaza dirección con marcas huérfanas, controles o exceso: %s', (valor) => {
    expect(validarDireccion(valor)).not.toBeNull()
  })

  it.each([
    ['NIT', '900.' + ' '.repeat(50) + '123.456'],
    ['CEDULA_CIUDADANIA', '1.' + ' '.repeat(50) + '144.123.456'],
    ['CEDULA_EXTRANJERIA', 'a' + ' '.repeat(50) + '12'],
    ['PASAPORTE', 'ab' + ' '.repeat(50) + '123'],
    ['IDENTIFICACION_FISCAL_EXTRANJERA', 'RFC' + ' '.repeat(50) + 'X'.repeat(36)],
    ['OTRO', 'RFC' + ' '.repeat(50) + 'X'.repeat(36)],
  ] as const)('identificación %s: mide después de normalizar', (tipo, valor) => {
    expect(validarIdentificacion(tipo, valor)).toBeNull()
  })
})

import type { TipoIdentificacion } from './epica02'

/**
 * HT14-FE01: réplica en el cliente de backend/src/backend/core/validaciones.py,
 * para dar retroalimentación inmediata sin esperar al servidor. El backend
 * sigue siendo la fuente de verdad — estas reglas no deben ser más estrictas
 * que las suyas, solo adelantan el mismo resultado cuando es evidente.
 *
 * Cada función devuelve el mensaje de error (igual al que mostraría el 422
 * del backend) o `null` si el valor es válido. No normalizan ni transforman
 * el valor: esa parte sigue siendo responsabilidad exclusiva del backend.
 */

// H-07: mismo conjunto explícito de 17 espacios Unicode Zs que en Python.
const ESPACIOS_FORMATO = ' \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000'
const ESPACIOS_FORMATO_RE = new RegExp(`[${ESPACIOS_FORMATO}]+`, 'g')
const BORDES_ESPACIOS_FORMATO = new RegExp(`^[${ESPACIOS_FORMATO}]+|[${ESPACIOS_FORMATO}]+$`, 'g')
const SEPARADORES_NUMERICOS = new RegExp(`[.${ESPACIOS_FORMATO}]`, 'g')
const BASE_NUMERICA = /^\d{5,10}$/
const DIGITO = /^\d$/
const CEDULA_EXTRANJERIA = /^[A-Z0-9]{3,15}$/
const PASAPORTE = /^[A-Z0-9]{5,20}$/
const IDENTIFICACION_LIBRE = /^[A-Za-z0-9\-./ ]{3,40}$/
const ALFANUMERICO = /[A-Za-z0-9]/
const TELEFONO_LIGERO = /^\+?[\d \-().]+(?: *(?:ext\.?|extensi[oó]n|x) *\d{1,6})?$/i
const TELEFONO_CANONICO_CON_EXTENSION = /^\+[1-9][0-9]{1,14};ext=[0-9]{1,6}$/
// En JavaScript `\w` solo incluye ASCII, incluso con /u: tildes y eñes requieren \p{...}.
const CIUDAD = /^\p{L}\p{M}*(?:\p{L}\p{M}*|[ \-.'])*$/u
const LETRA = /\p{L}/u
const DIRECCION = /^(?:\p{L}\p{M}*|[\p{N} #\-.,/°º()'])+$/u
const ESPACIOS_UBICACION = /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g

function colapsarEspacios(valor: string): string {
  return recortarEspaciosFormato(valor).replace(ESPACIOS_FORMATO_RE, ' ').normalize('NFC')
}

export function recortarEspaciosFormato(valor: string): string {
  return valor.replace(BORDES_ESPACIOS_FORMATO, '')
}

export function normalizarBaseIdentificacion(valor: string): string {
  return valor.replace(SEPARADORES_NUMERICOS, '')
}

export function normalizarUbicacion(valor: string): string {
  // No usar trim/\s: podrían ocultar controles o formatos invisibles.
  return valor.replace(ESPACIOS_UBICACION, ' ').replace(/^ +| +$/g, '').normalize('NFC')
}

const PESOS_DV_NIT = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]

export function calcularDigitoVerificacionNit(base: string): number {
  let suma = 0
  const digitos = [...base].reverse()
  for (let i = 0; i < digitos.length && i < PESOS_DV_NIT.length; i++) {
    suma += Number(digitos[i]) * PESOS_DV_NIT[i]
  }
  const residuo = suma % 11
  return residuo < 2 ? residuo : 11 - residuo
}

export function validarDigitoVerificacionNit(base: string | null, valor: string): string | null {
  const digito = recortarEspaciosFormato(valor)
  if (!DIGITO.test(digito)) return 'El dígito de verificación debe ser un solo dígito'
  if (base && Number(digito) !== calcularDigitoVerificacionNit(base)) {
    return 'El dígito de verificación del NIT no es correcto'
  }
  return null
}

export function validarIdentificacion(tipo: TipoIdentificacion, valor: string): string | null {
  if (tipo === 'NIT') {
    const base = normalizarBaseIdentificacion(valor)
    if (!BASE_NUMERICA.test(base)) {
      return 'El NIT debe tener entre 5 y 10 dígitos, sin el dígito de verificación (se registra en su propio campo)'
    }
    return null
  }
  if (tipo === 'CEDULA_CIUDADANIA') {
    const cedula = normalizarBaseIdentificacion(valor)
    if (!BASE_NUMERICA.test(cedula)) return 'La cédula de ciudadanía debe tener entre 5 y 10 dígitos'
    return null
  }
  if (tipo === 'CEDULA_EXTRANJERIA') {
    const cedula = valor.replace(ESPACIOS_FORMATO_RE, '').toUpperCase()
    if (!CEDULA_EXTRANJERIA.test(cedula)) {
      return 'La cédula de extranjería debe tener entre 3 y 15 letras o dígitos'
    }
    return null
  }
  if (tipo === 'PASAPORTE') {
    const pasaporte = valor.replace(ESPACIOS_FORMATO_RE, '').toUpperCase()
    if (!PASAPORTE.test(pasaporte)) return 'El pasaporte debe tener entre 5 y 20 letras o dígitos'
    return null
  }
  const identificacion = colapsarEspacios(valor)
  if (!IDENTIFICACION_LIBRE.test(identificacion) || !ALFANUMERICO.test(identificacion)) {
    return 'La identificación debe tener entre 3 y 40 caracteres: letras, dígitos, espacios, guion, punto o barra; incluya al menos una letra o dígito'
  }
  return null
}

/**
 * Validación liviana: solo descarta formatos evidentemente inválidos
 * (letras, símbolos fuera de lo esperado, muy corto/largo). El backend usa
 * `phonenumbers` para validar el plan de numeración real de cada país; no
 * se replica aquí para no agregar una dependencia nueva solo para esto — el
 * 422 del servidor sigue siendo quien rechaza un número con formato
 * razonable pero inválido.
 */
export function validarTelefono(valor: string): string | null {
  const telefono = recortarEspaciosFormato(valor).replace(ESPACIOS_FORMATO_RE, ' ')
  if (!(
    (TELEFONO_LIGERO.test(telefono) && (telefono.match(/\d/g)?.length ?? 0) >= 5)
    || TELEFONO_CANONICO_CON_EXTENSION.test(telefono)
  )) {
    return 'Ingrese un teléfono válido. Para números fuera de Colombia, incluya el indicativo con + (por ejemplo, +34 912 345 678)'
  }
  return null
}

export function validarCiudad(valor: string): string | null {
  const ciudad = normalizarUbicacion(valor)
  const longitud = [...ciudad].length
  if (!(longitud >= 2 && longitud <= 120 && CIUDAD.test(ciudad))) {
    return 'La ciudad debe tener entre 2 y 120 caracteres y contener solo letras, espacios, guion, punto o apóstrofo'
  }
  return null
}

export function validarDireccion(valor: string): string | null {
  const direccion = normalizarUbicacion(valor)
  const referencias = direccion.split(/[,/]/)
  const tieneReferencia = /\p{Nd}/u.test(direccion)
    || (referencias.length >= 2 && referencias.every((referencia) => LETRA.test(referencia)))
  const longitud = [...direccion].length
  if (
    !(
      longitud >= 5
      && longitud <= 200
      && DIRECCION.test(direccion)
      && LETRA.test(direccion)
      && tieneReferencia
    )
  ) {
    return "La dirección debe tener entre 5 y 200 caracteres, incluir letras y un número o dos referencias separadas por coma o barra. Use solo letras, dígitos, espacios y los signos # - . , / ° º ( ) '"
  }
  return null
}

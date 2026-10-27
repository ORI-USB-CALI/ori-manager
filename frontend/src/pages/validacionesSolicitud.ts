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

const SEPARADORES_NUMERICOS = /[.\s]/g
const BASE_NUMERICA = /^\d{5,10}$/
const DIGITO = /^\d$/
const CEDULA_EXTRANJERIA = /^[A-Z0-9]{3,15}$/
const PASAPORTE = /^[A-Z0-9]{5,20}$/
const IDENTIFICACION_LIBRE = /^[A-Za-z0-9\-./ ]{3,40}$/
const TELEFONO_LIGERO = /^\+?[\d\s\-().]{5,25}$/
const CIUDAD = /^[^\W\d_](?:[^\W\d_]|[\s\-.'])*$/u
const LETRA = /[^\W\d_]/u
const DIRECCION = /^(?:[^\W_]|[\s#\-.,/°º()'])+$/u

function colapsarEspacios(valor: string): string {
  return valor.trim().split(/\s+/).join(' ')
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

export function validarDigitoVerificacionNit(base: string, valor: string): string | null {
  const digito = valor.trim()
  if (!DIGITO.test(digito)) return 'El dígito de verificación debe ser un solo dígito'
  if (Number(digito) !== calcularDigitoVerificacionNit(base)) {
    return 'El dígito de verificación del NIT no es correcto'
  }
  return null
}

export function validarIdentificacion(tipo: TipoIdentificacion, valor: string): string | null {
  if (tipo === 'NIT') {
    const base = valor.replace(SEPARADORES_NUMERICOS, '')
    if (!BASE_NUMERICA.test(base)) {
      return 'El NIT debe tener entre 5 y 10 dígitos, sin el dígito de verificación (se registra en su propio campo)'
    }
    return null
  }
  if (tipo === 'CEDULA_CIUDADANIA') {
    const cedula = valor.replace(SEPARADORES_NUMERICOS, '')
    if (!BASE_NUMERICA.test(cedula)) return 'La cédula de ciudadanía debe tener entre 5 y 10 dígitos'
    return null
  }
  if (tipo === 'CEDULA_EXTRANJERIA') {
    const cedula = valor.replace(/\s/g, '').toUpperCase()
    if (!CEDULA_EXTRANJERIA.test(cedula)) {
      return 'La cédula de extranjería debe tener entre 3 y 15 letras o dígitos'
    }
    return null
  }
  if (tipo === 'PASAPORTE') {
    const pasaporte = valor.replace(/\s/g, '').toUpperCase()
    if (!PASAPORTE.test(pasaporte)) return 'El pasaporte debe tener entre 5 y 20 letras o dígitos'
    return null
  }
  const identificacion = colapsarEspacios(valor)
  if (!IDENTIFICACION_LIBRE.test(identificacion)) {
    return 'La identificación debe tener entre 3 y 40 caracteres: letras, dígitos, espacios, guion, punto o barra'
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
  const telefono = valor.trim()
  if (!TELEFONO_LIGERO.test(telefono)) {
    return 'Ingrese un teléfono válido. Para números fuera de Colombia, incluya el indicativo con + (por ejemplo, +34 912 345 678)'
  }
  return null
}

export function validarCiudad(valor: string): string | null {
  const ciudad = colapsarEspacios(valor)
  if (!(ciudad.length >= 2 && ciudad.length <= 120 && CIUDAD.test(ciudad))) {
    return 'La ciudad debe tener entre 2 y 120 caracteres y contener solo letras, espacios, guion, punto o apóstrofo'
  }
  return null
}

export function validarDireccion(valor: string): string | null {
  const direccion = colapsarEspacios(valor)
  if (
    !(
      direccion.length >= 5
      && direccion.length <= 200
      && DIRECCION.test(direccion)
      && LETRA.test(direccion)
    )
  ) {
    return 'La dirección debe tener entre 5 y 200 caracteres, incluir letras y usar solo letras, dígitos, espacios y los signos # - . , / ° ( )'
  }
  return null
}

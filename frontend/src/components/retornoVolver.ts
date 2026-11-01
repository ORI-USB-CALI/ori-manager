import type { Location } from 'react-router-dom'

/* HT-12: contrato del retorno entre vistas. La vista de origen deja en
   `location.state.volver` a dónde debe regresar la acción Volver; la vista de
   destino solo lo usa si es una ruta interna segura y, si no, cae en su
   destino alternativo (acceso directo, recarga o enlace externo). */

export interface Retorno {
  to: string
  texto: string
  /** Retorno propio de la pantalla a la que se vuelve, ya validado. */
  estado?: EstadoVolver
}

export interface EstadoVolver {
  volver: Retorno
}

const LONGITUD_MAXIMA_RUTA = 2048
const LONGITUD_MAXIMA_TEXTO = 80
const MAXIMO_RETORNOS = 8

export function esRutaInternaSegura(ruta: unknown): ruta is string {
  return typeof ruta === 'string'
    && ruta.length <= LONGITUD_MAXIMA_RUTA
    && ruta.startsWith('/')
    // `//host` y `/\host` son URLs absolutas para el navegador.
    && !ruta.startsWith('//')
    && !ruta.startsWith('/\\')
    // eslint-disable-next-line no-control-regex
    && !/[\u0000-\u001f\u007f]/.test(ruta)
}

function leerRetorno(estado: unknown): Retorno | null {
  if (typeof estado !== 'object' || estado === null || !('volver' in estado)) return null
  const volver = (estado as { volver: unknown }).volver
  if (typeof volver !== 'object' || volver === null) return null
  const { to, texto } = volver as Partial<Record<keyof Retorno, unknown>>
  if (!esRutaInternaSegura(to)) return null
  if (typeof texto !== 'string' || !texto.trim() || texto.length > LONGITUD_MAXIMA_TEXTO) return null
  return { to, texto }
}

/** Descarta campos ajenos al contrato y limita estados profundos o cíclicos.
 * Si se vuelve a visitar una pantalla, recupera su retorno anterior: nunca
 * construye un recorrido circular entre pantallas secundarias. */
export function retornoSeguro(estado: unknown, rutaActual?: string): Retorno | null {
  const retornos: Retorno[] = []
  const visitados = new Set<unknown>()
  let actual = estado
  for (let nivel = 0; nivel < MAXIMO_RETORNOS; nivel++) {
    if (visitados.has(actual)) break
    visitados.add(actual)
    const retorno = leerRetorno(actual)
    if (!retorno) break
    retornos.push(retorno)
    actual = (actual as EstadoVolver).volver.estado
  }

  // La búsqueda es contexto de la pantalla, no una pantalla diferente.
  const pantalla = (ruta: string) => ruta.split(/[?#]/)[0]
  const cadena: Retorno[] = []
  for (const retorno of retornos.reverse()) {
    if (rutaActual && pantalla(retorno.to) === pantalla(rutaActual)) break
    // Conserva la aparición más antigua y su origen al revisitar una pantalla.
    const repetida = cadena.findIndex((anterior) => pantalla(anterior.to) === pantalla(retorno.to))
    if (repetida >= 0) cadena.splice(0, repetida)
    else cadena.unshift(retorno)
  }
  return cadena.reduceRight<Retorno | null>((anterior, retorno) => anterior
    ? { ...retorno, estado: { volver: anterior } }
    : retorno, null)
}

/** Estado para un enlace que sale de `ubicacion` y debe poder regresar a ella, con sus filtros. */
export function volverA(ubicacion: Pick<Location, 'pathname' | 'search'> & { state?: unknown }, texto: string): EstadoVolver {
  const anterior = retornoSeguro(ubicacion.state, ubicacion.pathname)
  return { volver: {
    to: `${ubicacion.pathname}${ubicacion.search}`, texto,
    ...(anterior ? { estado: { volver: anterior } } : {}),
  } }
}

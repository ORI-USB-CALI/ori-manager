import type { Location } from 'react-router-dom'

/* HT-12: contrato del retorno entre vistas. La vista de origen deja en
   `location.state.volver` a dónde debe regresar la acción Volver; la vista de
   destino solo lo usa si es una ruta interna segura y, si no, cae en su
   destino alternativo (acceso directo, recarga o enlace externo). */

export interface Retorno {
  to: string
  texto: string
}

export interface EstadoVolver {
  volver: Retorno
}

const LONGITUD_MAXIMA_RUTA = 2048
const LONGITUD_MAXIMA_TEXTO = 80

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

export function retornoSeguro(estado: unknown): Retorno | null {
  if (typeof estado !== 'object' || estado === null || !('volver' in estado)) return null
  const volver = (estado as { volver: unknown }).volver
  if (typeof volver !== 'object' || volver === null) return null
  const { to, texto } = volver as Partial<Record<keyof Retorno, unknown>>
  if (!esRutaInternaSegura(to)) return null
  if (typeof texto !== 'string' || !texto.trim() || texto.length > LONGITUD_MAXIMA_TEXTO) return null
  return { to, texto }
}

/** Estado para un enlace que sale de `ubicacion` y debe poder regresar a ella, con sus filtros. */
export function volverA(ubicacion: Pick<Location, 'pathname' | 'search'>, texto: string): EstadoVolver {
  return { volver: { to: `${ubicacion.pathname}${ubicacion.search}`, texto } }
}

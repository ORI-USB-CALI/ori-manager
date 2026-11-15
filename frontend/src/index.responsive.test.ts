/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { URL as NodeURL } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * HT-18 CA-04: presentación de la bitácora y del visor en escritorio, tablet y móvil.
 *
 * jsdom no aplica media queries ni calcula diseño, así que se leen las reglas
 * reales de index.css. La comprobación visual por resolución sigue siendo manual.
 */
interface Regla {
  media: string | null
  selector: string
  declaraciones: Array<[propiedad: string, valor: string]>
}

function leerReglas(css: string, media: string | null = null): Regla[] {
  const reglas: Regla[] = []
  let inicio = 0
  while (inicio < css.length) {
    const abre = css.indexOf('{', inicio)
    if (abre === -1) break
    let fin = abre + 1
    for (let profundidad = 1; fin < css.length && profundidad > 0; fin += 1) {
      if (css[fin] === '{') profundidad += 1
      else if (css[fin] === '}') profundidad -= 1
    }
    const cabecera = css.slice(inicio, abre).trim()
    const cuerpo = css.slice(abre + 1, fin - 1)
    if (cabecera.startsWith('@media')) {
      reglas.push(...leerReglas(cuerpo, cabecera.replace(/^@media\s*/, '')))
    } else if (!cabecera.startsWith('@')) {
      const declaraciones = cuerpo.split(';').map((linea) => linea.trim()).filter(Boolean).map((linea) => {
        const separador = linea.indexOf(':')
        return [linea.slice(0, separador).trim(), linea.slice(separador + 1).trim()] as [string, string]
      })
      for (const selector of cabecera.split(',')) {
        reglas.push({ media, selector: selector.trim().replace(/\s+/g, ' '), declaraciones })
      }
    }
    inicio = fin
  }
  return reglas
}

const REGLAS = leerReglas(
  readFileSync(new NodeURL('./index.css', import.meta.url), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^@import[^;]*;/gm, ''),
)

/** Valores declarados para una propiedad, en orden: el último es el que aplica. */
function valores(selector: string, propiedad: string, media: string | null = null): string[] {
  return REGLAS
    .filter((regla) => regla.selector === selector && regla.media === media)
    .flatMap((regla) => regla.declaraciones)
    .filter(([nombre]) => nombre === propiedad)
    .map(([, valor]) => valor)
}

const TABLET = '(max-width: 1024px)'
const TABLET_VERTICAL = '(max-width: 768px)'
const MOVIL = '(max-width: 640px)'

describe('HT-18 CA-04: bitácora legible en escritorio, tablet y móvil', () => {
  it('la tabla conserva su ancho y se desplaza dentro de su contenedor en cada resolución', () => {
    expect(valores('.bitacora-tabla-container', 'overflow-x')).toEqual(['auto'])
    expect(valores('.bitacora-tabla-container', 'max-width')).toEqual(['100%'])
    expect(valores('.bitacora-tabla', 'min-width')).toEqual(['1720px'])
    expect(valores('.bitacora-tabla', 'min-width', TABLET)).toEqual(['1640px'])
    expect(valores('.bitacora-tabla', 'min-width', TABLET_VERTICAL)).toEqual(['1560px'])
  })

  it('las resoluciones menores solo ajustan ancho mínimo y relleno, sin alterar el ajuste de texto', () => {
    const responsive = REGLAS.filter((regla) => regla.media !== null && regla.selector.includes('bitacora'))

    expect(responsive.map((regla) => regla.media).sort())
      .toEqual([TABLET, TABLET_VERTICAL, TABLET_VERTICAL, TABLET_VERTICAL])
    for (const regla of responsive) {
      for (const [propiedad] of regla.declaraciones) {
        expect(['min-width', 'padding']).toContain(propiedad)
      }
    }
  })

  it('"Automática" nunca se parte: la naturaleza no admite saltos en ninguna regla', () => {
    const naturaleza = REGLAS.filter((regla) => regla.selector.includes('bitacora-col-naturaleza'))

    expect(naturaleza).toHaveLength(1)
    expect(naturaleza[0].media).toBeNull()
    expect(valores('.bitacora-tabla .bitacora-col-naturaleza', 'white-space')).toEqual(['nowrap'])
    expect(valores('.bitacora-tabla .bitacora-col-naturaleza', 'overflow-wrap')).toEqual(['normal'])
    expect(valores('.bitacora-tabla .bitacora-col-naturaleza', 'word-break')).toEqual(['normal'])
  })

  it('valores extensos como "BORRADOR_GUARDADO" solo se ajustan entre palabras y en una columna con ancho propio', () => {
    for (const columna of ['evento', 'etapa']) {
      const selector = `.bitacora-tabla .bitacora-col-${columna}`
      expect(valores(selector, 'min-width')).toEqual(['14rem'])
      expect(valores(selector, 'overflow-wrap')).toEqual(['break-word'])
      expect(valores(selector, 'word-break')).toEqual(['normal'])
    }
    expect(valores('.bitacora-tabla thead th', 'white-space')).toEqual(['nowrap'])
  })
})

describe('HT-18 CA-04: visor de documentos utilizable en escritorio, tablet y móvil', () => {
  it('en escritorio y tablet el visor cabe en la ventana con margen', () => {
    expect(valores('.modal-preview', 'width')).toEqual(['min(1000px, calc(100% - 32px))'])
    expect(valores('.modal-preview', 'height')).toEqual(['min(90vh, 850px)'])
    expect(valores('.modal-preview', 'max-height')).toEqual(['calc(100vh - 32px)'])
  })

  it('el documento ocupa el espacio disponible sin desbordar el visor', () => {
    expect(valores('.modal-preview .modal-section', 'min-height')).toEqual(['0'])
    expect(valores('.modal-preview .modal-section', 'overflow')).toEqual(['auto'])
    expect(valores('.preview-iframe', 'width')).toEqual(['100%'])
    expect(valores('.preview-iframe', 'height')).toEqual(['100%'])
  })

  it('en móvil el visor usa toda la pantalla y mantiene visibles el título y las acciones', () => {
    expect(valores('.modal-preview', 'width', MOVIL)).toEqual(['100%'])
    expect(valores('.modal-preview', 'height', MOVIL).at(-1)).toBe('100dvh')
    expect(valores('.modal-preview', 'max-height', MOVIL).at(-1)).toBe('100dvh')
    expect(valores('.modal-preview .modal-header', 'flex-shrink', MOVIL)).toEqual(['0'])
    expect(valores('.modal-preview .modal-acciones', 'flex-shrink', MOVIL)).toEqual(['0'])
    expect(valores('.modal-preview .modal-header h2', 'overflow-wrap', MOVIL)).toEqual(['anywhere'])
  })

  it('los estados de error (403/404) reacomodan sus acciones en pantallas angostas', () => {
    expect(valores('.preview-acciones-error', 'flex-wrap')).toEqual(['wrap'])
    expect(valores('.modal-preview .preview-estado', 'padding', MOVIL)).toEqual(['16px'])
  })
})

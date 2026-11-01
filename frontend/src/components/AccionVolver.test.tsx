/// <reference types="node" />
import { readFileSync } from 'node:fs'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TableroConveniosPage } from '../pages/TableroConveniosPage'
import type { TableroConvenios } from '../pages/epica02'
import { AccionVolver } from './AccionVolver'
import { type EstadoVolver, esRutaInternaSegura, retornoSeguro, volverA } from './retornoVolver'

const ALTERNATIVO = { to: '/convenios/tablero', texto: 'Volver al tablero de convenios' }

function Ubicacion() {
  const { pathname, search, state } = useLocation()
  return <><output data-testid="ubicacion">{`${pathname}${search}`}</output><output data-testid="estado">{JSON.stringify(state)}</output></>
}

function renderizar(entrada: string | { pathname: string; state?: unknown }, estado?: unknown) {
  render(
    <MemoryRouter initialEntries={[entrada]}>
      <Routes>
        <Route path="/convenios/:id" element={<><AccionVolver alternativo={ALTERNATIVO} estado={estado} /><h1>Detalle</h1></>} />
        <Route path="/convenios/tablero" element={<Ubicacion />} />
        <Route path="*" element={<Ubicacion />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('AccionVolver (HT-12)', () => {
  it('usa el destino alternativo cuando se accede directamente a la vista', () => {
    renderizar('/convenios/41')
    const volver = screen.getByRole('link', { name: 'Volver al tablero de convenios' })
    expect(volver.getAttribute('href')).toBe('/convenios/tablero')
  })

  it('regresa al contexto de origen con sus filtros', async () => {
    renderizar({
      pathname: '/convenios/41',
      state: { volver: { to: '/convenios?buscar=movilidad&estado=VIGENTE', texto: 'Volver a la consulta de convenios' } },
    })
    await userEvent.click(screen.getByRole('link', { name: 'Volver a la consulta de convenios' }))
    expect(screen.getByTestId('ubicacion').textContent).toBe('/convenios?buscar=movilidad&estado=VIGENTE')
  })

  it.each([
    ['URL absoluta', { to: 'https://externo.example.com', texto: 'Volver' }],
    ['URL sin protocolo', { to: '//externo.example.com', texto: 'Volver' }],
    ['barra invertida', { to: '/\\externo.example.com', texto: 'Volver' }],
    ['javascript:', { to: 'javascript:alert(1)', texto: 'Volver' }],
    ['ruta relativa', { to: 'convenios', texto: 'Volver' }],
    ['caracteres de control', { to: '/convenios\n', texto: 'Volver' }],
    ['texto vacío', { to: '/convenios', texto: '   ' }],
    ['tipos inválidos', { to: 41, texto: null }],
  ])('ignora un retorno inseguro (%s) y usa el alternativo', (_caso, volver) => {
    renderizar({ pathname: '/convenios/41', state: { volver } })
    expect(screen.getByRole('link', { name: 'Volver al tablero de convenios' }).getAttribute('href')).toBe('/convenios/tablero')
  })

  it('es el primer elemento enfocable de la vista y se activa con el teclado', async () => {
    const usuario = userEvent.setup()
    renderizar('/convenios/41')
    await usuario.tab()
    const volver = screen.getByRole('link', { name: 'Volver al tablero de convenios' })
    expect(document.activeElement).toBe(volver)
    expect(volver.compareDocumentPosition(screen.getByRole('heading', { name: 'Detalle' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await usuario.keyboard('{Enter}')
    expect(screen.getByTestId('ubicacion').textContent).toBe('/convenios/tablero')
  })

  it('mantiene la misma presentación en todas las vistas', () => {
    renderizar('/convenios/41')
    const volver = screen.getByRole('link', { name: 'Volver al tablero de convenios' })
    expect(volver.className).toBe('btn accion-volver')
    expect(volver.parentElement?.className).toBe('accion-volver-barra')
    // La flecha es decorativa: el nombre accesible es solo el texto.
    expect(volver.querySelector('[aria-hidden="true"]')?.textContent).toBe('←')
  })

  it.each([
    [{ volver: { to: '/convenios?buscar=x', texto: 'Consulta' }, ajeno: true }, { volver: { to: '/convenios?buscar=x', texto: 'Consulta' } }],
    [{ volver: { to: '//externo.example', texto: 'Salir' } }, null],
  ])('la propiedad estado mantiene solo el contrato validado (%j)', async (estado, esperado) => {
    renderizar('/convenios/41', estado)
    await userEvent.click(screen.getByRole('link', { name: 'Volver al tablero de convenios' }))
    expect(screen.getByTestId('estado').textContent).toBe(JSON.stringify(esperado))
  })
})

describe('retorno seguro', () => {
  it('construye el retorno con la ruta y la búsqueda de la vista de origen', () => {
    expect(volverA({ pathname: '/convenios', search: '?buscar=x' }, 'Volver a la consulta de convenios'))
      .toEqual({ volver: { to: '/convenios?buscar=x', texto: 'Volver a la consulta de convenios' } })
  })

  it('solo acepta rutas internas', () => {
    expect(esRutaInternaSegura('/convenios/tablero')).toBe(true)
    expect(esRutaInternaSegura(`/${'a'.repeat(2048)}`)).toBe(false)
    expect(retornoSeguro(null)).toBeNull()
    expect(retornoSeguro({ volver: 'texto' })).toBeNull()
  })

  it('propaga exclusivamente retornos validados y descarta un ancestro externo', () => {
    const estado = { secreto: 'no propagar', volver: {
      to: '/convenios/41?extra=1', texto: 'Volver al convenio', inyectado: true,
      estado: { volver: { to: '//externo.example', texto: 'Salir' }, otro: true },
    } }
    expect(volverA({ pathname: '/convenios/41/elaboracion', search: '', state: estado }, 'Volver al proyecto'))
      .toEqual({ volver: { to: '/convenios/41/elaboracion', texto: 'Volver al proyecto', estado: {
        volver: { to: '/convenios/41?extra=1', texto: 'Volver al convenio' },
      } } })
  })

  it('recorta autorreferencias y estados excesivamente profundos sin lanzar errores', () => {
    const ciclico: EstadoVolver = { volver: { to: '/convenios', texto: 'Consulta' } }
    ciclico.volver.estado = ciclico
    expect(retornoSeguro(ciclico)).toEqual({ to: '/convenios', texto: 'Consulta' })
    let profundo: EstadoVolver = ciclico
    for (let i = 0; i < 100; i++) profundo = { volver: { to: `/convenios/${i}`, texto: 'Volver', estado: profundo } }
    let retorno = retornoSeguro(profundo)
    let niveles = 0
    while (retorno) { niveles++; retorno = retorno.estado?.volver ?? null }
    expect(niveles).toBe(8)
  })

  it('recupera el origen anterior al revisitar una pantalla, incluso con otra búsqueda', () => {
    const origen = volverA({ pathname: '/renovaciones', search: '?estado=PENDIENTE_DE_DECISION' }, 'Renovaciones')
    const detalle = volverA({ pathname: '/convenios/41', search: '?pestana=historial', state: origen }, 'Detalle')
    const proyecto = volverA({ pathname: '/convenios/41/elaboracion', search: '', state: detalle }, 'Proyecto')
    const version = volverA({ pathname: '/convenios/41/versiones/1', search: '', state: proyecto }, 'Versión')
    expect(retornoSeguro(version, '/convenios/41/elaboracion')).toEqual(detalle.volver)
    expect(retornoSeguro(detalle, '/convenios/41')).toEqual(origen.volver)
  })
})

/* CA-01: contraste WCAG 2.1 AA del texto (4.5:1) y del borde (3:1) de la
   acción, calculado con los valores reales de las hojas de estilo. */
describe('contraste de la acción Volver', () => {
  // Vitest no procesa CSS: se leen los archivos reales (rutas relativas a frontend/).
  const variables = readFileSync('src/assets/variables.css', 'utf8')
  const estilos = readFileSync('src/index.css', 'utf8')

  function variable(nombre: string) {
    const valor = new RegExp(`${nombre}:\\s*(#[0-9a-f]{6})`, 'i').exec(variables)?.[1]
    if (!valor) throw new Error(`No existe la variable ${nombre}`)
    return valor
  }

  function luminancia(hex: string) {
    const [r, g, b] = [1, 3, 5].map((i) => {
      const canal = parseInt(hex.slice(i, i + 2), 16) / 255
      return canal <= 0.03928 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }

  function contraste(a: string, b: string) {
    const [claro, oscuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
    return (claro + 0.05) / (oscuro + 0.05)
  }

  function regla(selector: string) {
    const cuerpo = new RegExp(`\\n${selector.replace('.', '\\.')}\\s*\\{([^}]*)\\}`).exec(estilos)?.[1]
    if (!cuerpo) throw new Error(`No existe la regla ${selector}`)
    return cuerpo
  }

  it('usa texto y borde oscuros sobre la superficie clara', () => {
    const cuerpo = regla('.accion-volver')
    expect(cuerpo).toMatch(/background:\s*var\(--bg-surface\)/)
    expect(cuerpo).toMatch(/color:\s*var\(--text-primary\)/)
    expect(cuerpo).toMatch(/border:\s*2px solid var\(--text-primary\)/)
  })

  it.each(['--bg-surface', '--bg-main'])('cumple 4.5:1 sobre %s (reposo, hover y foco)', (fondo) => {
    expect(contraste(variable('--text-primary'), variable(fondo))).toBeGreaterThanOrEqual(4.5)
  })

  it('el borde se distingue del fondo de la página (3:1)', () => {
    expect(contraste(variable('--text-primary'), variable('--bg-main'))).toBeGreaterThanOrEqual(3)
  })

  it('mantiene un foco oscuro de 3px separado del borde, con contraste de al menos 3:1', () => {
    const foco = regla('.accion-volver:focus-visible')
    expect(foco).toMatch(/outline:\s*3px solid var\(--text-primary\)/)
    expect(foco).toMatch(/outline-offset:\s*2px/)
    expect(contraste(variable('--text-primary'), variable('--bg-main'))).toBeGreaterThanOrEqual(3)
  })
})

/* FE-02: navegación desde el Tablero hasta el detalle y de regreso. */
describe('navegación desde el Tablero', () => {
  it('el detalle regresa al tablero desde el que se abrió', async () => {
    const tablero: TableroConvenios = {
      etapas: [{ id: 1, codigo: 'ELABORACION', nombre: 'Elaboración', orden: 1, area_responsable: 'ORI' }],
      convenios: [{
        id: 41, codigo: 'CON-041', estado: 'EN_TRAMITE', etapa_actual: { id: 1, codigo: 'ELABORACION', nombre: 'Elaboración', orden: 1, area_responsable: 'ORI' },
        aliado: null, aliado_propuesto: 'Universidad Aliada', responsable: null, puede_ver_detalle: true,
      }],
    }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(tablero), { status: 200, headers: { 'Content-Type': 'application/json' } })))
    const usuario = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={['/convenios/tablero']}>
          <Routes>
            <Route path="/convenios/tablero" element={<TableroConveniosPage />} />
            <Route path="/convenios/:id" element={<AccionVolver alternativo={{ to: '/convenios', texto: 'Volver a la consulta de convenios' }} />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await usuario.click(await screen.findByRole('link', { name: 'Ver detalle' }))
    await usuario.click(screen.getByRole('link', { name: 'Volver al tablero de convenios' }))
    expect(await screen.findByRole('heading', { name: 'Tablero de convenios' })).toBeTruthy()
  })
})

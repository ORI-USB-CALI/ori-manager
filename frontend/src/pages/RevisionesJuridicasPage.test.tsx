import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RevisionesJuridicasPage } from './RevisionesJuridicasPage'

/**
 * HT-06 FE-02: la bandeja debe identificar los convenios igual que su página de
 * detalle. Quedó fuera del barrido inicial de FE-01 y ninguna prueba lo
 * detectaba, así que un revisor veía `#41` en la lista y
 * `Convenio provisional #41` al entrar al mismo convenio.
 */
const SIN_CODIGO = {
  revision_id: 1,
  convenio_id: 41,
  codigo_convenio: null,
  solicitud_consecutivo: 'SOL-00000041',
  objeto: 'Movilidad académica',
  tipo_convenio: { id: 1, nombre: 'Marco' },
  responsable: { id: 7, nombre_completo: 'Revisora Jurídica', correo: 'revisora@example.com' },
  fecha_recepcion: '2026-10-20T15:00:00Z',
  instancia_juridica: 1,
  numero_ronda: 1,
  version_numero: 1,
}

const CON_CODIGO = {
  ...SIN_CODIGO,
  revision_id: 2,
  convenio_id: 55,
  codigo_convenio: 'USB-ORI-2026-00007',
  objeto: 'Doble titulación',
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function Ubicacion() {
  return <output data-testid="busqueda-url">{useLocation().search}</output>
}

function preparar(items: unknown[], entrada = '/revisiones-juridicas') {
  const fetch = vi.fn(async () =>
    new Response(JSON.stringify(items), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  })
  render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[entrada]}>
        <Ubicacion />
        <RevisionesJuridicasPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('RevisionesJuridicasPage identifica los convenios (HT-06 FE-02, CA-01)', () => {
  it('muestra la referencia provisional de un convenio sin código', async () => {
    preparar([SIN_CODIGO])

    expect(await screen.findByText('Convenio provisional #41')).toBeTruthy()
    // El formato anterior era un id pelado.
    expect(screen.queryByText('#41')).toBeNull()
  })

  it('muestra el código institucional cuando el convenio ya está formalizado', async () => {
    preparar([CON_CODIGO])

    expect(await screen.findByText('USB-ORI-2026-00007')).toBeTruthy()
  })

  it('el buscador local encuentra un convenio por su referencia provisional', async () => {
    const usuario = preparar([SIN_CODIGO, CON_CODIGO])
    await screen.findByText('Convenio provisional #41')

    // El texto que indexa el buscador debe ser el mismo que se muestra: antes
    // era el id pelado, así que buscar "provisional" no encontraba nada.
    await usuario.type(screen.getByRole('searchbox'), 'provisional')

    expect(screen.getByText('Convenio provisional #41')).toBeTruthy()
    expect(screen.queryByText('USB-ORI-2026-00007')).toBeNull()
  })

  it('el buscador local sigue encontrando por código institucional', async () => {
    const usuario = preparar([SIN_CODIGO, CON_CODIGO])
    await screen.findByText('USB-ORI-2026-00007')

    await usuario.type(screen.getByRole('searchbox'), 'USB-ORI-2026-00007')

    expect(screen.getByText('USB-ORI-2026-00007')).toBeTruthy()
    expect(screen.queryByText('Convenio provisional #41')).toBeNull()
  })
})

describe('HT-12: filtros jurídicos persistentes en URL', () => {
  it('conserva las diez columnas, datos completos y una región desplazable enfocable', async () => {
    const objeto = 'Cooperación académica extensa\nSegunda línea del objeto completo'
    preparar([{ ...SIN_CODIGO, objeto }, { ...CON_CODIGO, instancia_juridica: 2, numero_ronda: 3, version_numero: 5 }])
    const tabla = await screen.findByRole('table', { name: 'Revisiones jurídicas' })
    expect(within(tabla).getAllByRole('columnheader').map((celda) => celda.textContent)).toEqual([
      'Convenio', 'Solicitud origen', 'Objeto', 'Tipo convenio', 'Revisión', 'Ronda', 'Versión', 'Responsable', 'Fecha de recepción', 'Acciones',
    ])
    for (const encabezado of within(tabla).getAllByRole('columnheader')) expect(encabezado.getAttribute('scope')).toBe('col')
    const filas = within(tabla).getAllByRole('row').slice(1)
    expect(filas.map((fila) => within(fila).getAllByRole('cell').length)).toEqual([10, 10])
    expect(filas[0].children[2].textContent).toBe(objeto)
    expect(filas[0].children[7].textContent).toContain(SIN_CODIGO.responsable.correo)
    expect(filas[0].children[4].textContent).toBe('1 de 2')
    expect(filas[1].children[4].textContent).toBe('2 de 2')
    expect(filas[1].children[5].textContent).toBe('3')
    expect(filas[1].children[6].textContent).toBe('5')
    expect(tabla.classList.contains('tabla-densa')).toBe(true)
    const region = screen.getByRole('region', { name: 'Revisiones jurídicas' })
    expect(region.tabIndex).toBe(0)
    expect(region.classList.contains('table-container')).toBe(true)
    expect(region.contains(tabla)).toBe(true)
  })

  it('actualiza y limpia solo sus filtros sin perder parámetros ajenos', async () => {
    const usuario = preparar([SIN_CODIGO, CON_CODIGO], '/revisiones-juridicas?extra=conservar')
    await screen.findByText('Convenio provisional #41')
    await usuario.type(screen.getByRole('searchbox'), 'provisional')
    await usuario.selectOptions(screen.getByLabelText('Tipo convenio'), 'Marco')
    await usuario.selectOptions(screen.getByLabelText('Responsable'), '7')
    const parametros = new URLSearchParams(screen.getByTestId('busqueda-url').textContent ?? '')
    expect(Object.fromEntries(parametros)).toEqual({ extra: 'conservar', buscar: 'provisional', tipo: 'Marco', responsable: '7' })
    await usuario.click(screen.getByRole('button', { name: /Limpiar/ }))
    expect(screen.getByTestId('busqueda-url').textContent).toBe('?extra=conservar')
    expect(screen.getByRole('searchbox')).toHaveProperty('value', '')
    expect(screen.getByText('USB-ORI-2026-00007')).toBeTruthy()
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Permiso, type Sesion } from '../auth/sesion'
import { LineaTiempoConvenio, type HitoLineaTiempo } from './LineaTiempoConvenio'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const formatoFechaHora = new Intl.DateTimeFormat('es-CO', { dateStyle: 'long', timeStyle: 'short' })

function preparar({ hitos, permisos = ['convenios.ver'], status = 200 }: {
  hitos?: HitoLineaTiempo[]; permisos?: Permiso[]; status?: number
}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const sesion: Sesion = {
    id: 1, correo: 'gestor@example.com', nombre_completo: 'Gestor', activo: true,
    tipo_usuario: 'INTERNO', rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos,
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  const cuerpo = status === 200 ? hitos ?? [] : { detail: 'Error' }
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(cuerpo), { status }))
  vi.stubGlobal('fetch', fetch)
  render(
    <QueryClientProvider client={cliente}>
      <LineaTiempoConvenio convenioId={7} />
    </QueryClientProvider>,
  )
  return { fetch }
}

async function hitosMostrados() {
  const lista = await screen.findByRole('list', { name: 'Hitos del convenio' })
  return within(lista).getAllByRole('listitem')
}

describe('LineaTiempoConvenio', () => {
  it('consulta la línea de tiempo del convenio', async () => {
    const { fetch } = preparar({ hitos: [] })

    await screen.findByText('El convenio aún no tiene hitos registrados.')

    expect(String(fetch.mock.calls[0][0])).toContain('/convenios/7/linea-tiempo')
  })

  it('muestra los hitos en el orden cronológico recibido con nombre y fecha', async () => {
    preparar({
      hitos: [
        { codigo: 'INICIO_ELABORACION', nombre: 'Inicio de elaboración', fecha: '2026-01-15T14:30:00Z', estado: 'COMPLETADO' },
        { codigo: 'ACTIVACION', nombre: 'Activación', fecha: '2026-03-02T16:00:00Z', estado: 'COMPLETADO' },
        { codigo: 'VENCIMIENTO', nombre: 'Vencimiento', fecha: '2028-01-01', estado: 'PROGRAMADO' },
      ],
    })

    const items = await hitosMostrados()

    expect(items.map((item) => item.querySelector('.timeline-titulo')?.textContent)).toEqual([
      'Inicio de elaboración', 'Activación', 'Vencimiento',
    ])
    expect(within(items[0]).getByText(formatoFechaHora.format(new Date('2026-01-15T14:30:00Z')))).toBeTruthy()
    expect(within(items[1]).getByText(formatoFechaHora.format(new Date('2026-03-02T16:00:00Z')))).toBeTruthy()
    expect(within(items[0]).getByText('Completado')).toBeTruthy()
  })

  it('muestra el vencimiento sin desfase de zona horaria', async () => {
    preparar({ hitos: [{ codigo: 'VENCIMIENTO', nombre: 'Vencimiento', fecha: '2028-01-01', estado: 'PROGRAMADO' }] })

    const [vencimiento] = await hitosMostrados()

    expect(within(vencimiento).getByText('1 de enero de 2028')).toBeTruthy()
    expect(within(vencimiento).getByRole('time').getAttribute('datetime')).toBe('2028-01-01')
  })

  it('identifica el vencimiento futuro', async () => {
    preparar({ hitos: [{ codigo: 'VENCIMIENTO', nombre: 'Vencimiento', fecha: '2028-01-01', estado: 'PROGRAMADO' }] })

    const [vencimiento] = await hitosMostrados()

    expect(within(vencimiento).getByText('Fecha futura')).toBeTruthy()
  })

  it('identifica un vencimiento ya cumplido', async () => {
    preparar({ hitos: [{ codigo: 'VENCIMIENTO', nombre: 'Vencimiento', fecha: '2024-06-30', estado: 'COMPLETADO' }] })

    const [vencimiento] = await hitosMostrados()

    expect(within(vencimiento).getByText('Vencido')).toBeTruthy()
  })

  it('muestra la activación pendiente sin fecha', async () => {
    preparar({
      hitos: [
        { codigo: 'INICIO_ELABORACION', nombre: 'Inicio de elaboración', fecha: '2026-01-15T14:30:00Z', estado: 'COMPLETADO' },
        { codigo: 'ACTIVACION', nombre: 'Activación', fecha: null, estado: 'PENDIENTE' },
      ],
    })

    const [, activacion] = await hitosMostrados()

    expect(within(activacion).getByText('Pendiente')).toBeTruthy()
    expect(within(activacion).getByText('Sin fecha registrada')).toBeTruthy()
    expect(within(activacion).queryByRole('time')).toBeNull()
    expect(within(activacion).queryByText('Completado')).toBeNull()
  })

  it('no consulta la línea de tiempo sin permiso para ver convenios', () => {
    const { fetch } = preparar({ hitos: [], permisos: [] })

    expect(fetch).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: 'Línea de tiempo' })).toBeNull()
  })

  it('informa cuando no se puede consultar la línea de tiempo', async () => {
    preparar({ status: 500 })

    expect((await screen.findByRole('alert')).textContent)
      .toBe('No fue posible consultar la línea de tiempo del convenio.')
  })
})

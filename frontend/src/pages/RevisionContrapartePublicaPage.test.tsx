import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { RevisionContrapartePublicaPage } from './RevisionContrapartePublicaPage'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  window.history.replaceState({}, '', '/')
})

function preparar() {
  window.history.replaceState({}, '', '/revision-contraparte#token=token-de-prueba')
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/acceso') ? {
      codigo_convenio: null, objeto: 'Convenio manual', contraparte: 'Entidad aliada',
      version_numero: 2, estado: 'PENDIENTE', correo_destino: 'representante@example.com',
      expira_en: '2027-01-01T12:00:00Z',
      contenido: { type: 'doc', content: [{ type: 'paragraph' }] },
    } : { estado: 'RESUELTA', resultado: url.endsWith('/aprobar') ? 'APROBADA' : 'DEVUELTA' },
  ), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={vi.fn()}>
        <RevisionContrapartePublicaPage />
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { fetch, usuario: userEvent.setup() }
}

describe('HT-03 revisión pública de contraparte', () => {
  it('identifica los campos obligatorios y no envía observaciones vacías ni una identidad incompleta', async () => {
    const { fetch, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Devolver con observaciones' }))
    const dialogo = screen.getByRole('dialog')
    const nombre = within(dialogo).getByRole('textbox', { name: 'Nombre *' }) as HTMLInputElement
    const cargo = within(dialogo).getByRole('textbox', { name: 'Cargo *' }) as HTMLInputElement
    const observacion = within(dialogo).getByRole('textbox', { name: 'Observación 1 *' }) as HTMLTextAreaElement
    for (const campo of [nombre, cargo, observacion]) {
      expect(campo.required).toBe(true)
      expect(campo.getAttribute('aria-required')).toBe('true')
      expect(document.getElementById(campo.getAttribute('aria-describedby')!)?.textContent).toContain('son obligatorios')
    }
    const confirmar = within(dialogo).getByRole('button', { name: 'Confirmar devolución' }) as HTMLButtonElement
    await usuario.type(nombre, 'Claudia Pérez')
    await usuario.type(cargo, 'Directora')
    expect(confirmar.disabled).toBe(true)
    await usuario.type(observacion, '  \n  ')
    expect(confirmar.disabled).toBe(true)
    await usuario.click(confirmar)
    expect(fetch).toHaveBeenCalledTimes(1)
    await usuario.clear(observacion)
    await usuario.type(observacion, 'Completar las obligaciones')
    await usuario.clear(nombre)
    await usuario.type(nombre, '   ')
    expect(confirmar.disabled).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('conserva observaciones múltiples, permite retirar una vacía y envía el contrato existente', async () => {
    const { fetch, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Devolver con observaciones' }))
    const dialogo = screen.getByRole('dialog')
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Nombre *' }), ' Claudia Pérez ')
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Cargo *' }), ' Directora ')
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Observación 1 *' }), ' Precisar el objeto ')
    const confirmar = within(dialogo).getByRole('button', { name: 'Confirmar devolución' }) as HTMLButtonElement
    expect(confirmar.disabled).toBe(false)
    await usuario.click(within(dialogo).getByRole('button', { name: '+ Agregar observación' }))
    expect(confirmar.disabled).toBe(true)
    await usuario.click(within(dialogo).getAllByRole('button', { name: 'Eliminar observación' })[1])
    expect(confirmar.disabled).toBe(false)
    await usuario.click(within(dialogo).getByRole('button', { name: '+ Agregar observación' }))
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Observación 2 *' }), ' Adjuntar el soporte ')
    await usuario.click(confirmar)
    expect(await screen.findByRole('heading', { name: 'Revisión enviada correctamente.' })).toBeTruthy()
    expect(fetch).toHaveBeenCalledWith('/api/public/revision-contraparte/devolver', expect.objectContaining({
      method: 'POST', body: JSON.stringify({
        token: 'token-de-prueba', nombre_firmante: 'Claudia Pérez', cargo_firmante: 'Directora',
        observaciones: ['Precisar el objeto', 'Adjuntar el soporte'],
      }),
    }))
    expect(window.location.hash).toBe('')
  })

  it('mantiene la identificación, la firma y la conformidad como requisitos para aprobar', async () => {
    const { fetch, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Aprobar elaboración de convenio' }))
    const dialogo = screen.getByRole('dialog')
    const confirmar = within(dialogo).getByRole('button', { name: 'Firmar y aprobar' }) as HTMLButtonElement
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Nombre del firmante *' }), ' Claudia Pérez ')
    await usuario.type(within(dialogo).getByRole('textbox', { name: 'Cargo *' }), ' Directora ')
    expect(confirmar.disabled).toBe(true)
    const canvas = within(dialogo).getByLabelText('Área para dibujar la firma de conformidad') as HTMLCanvasElement
    vi.spyOn(canvas, 'getContext').mockReturnValue({
      beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(),
    } as unknown as CanvasRenderingContext2D)
    const firma = 'data:image/png;base64,firma-de-prueba'
    vi.spyOn(canvas, 'toDataURL').mockReturnValue(firma)
    Object.defineProperty(canvas, 'setPointerCapture', { value: vi.fn() })
    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 10, clientY: 10 })
    fireEvent.pointerUp(canvas, { pointerId: 1 })
    expect(confirmar.disabled).toBe(true)
    await usuario.click(within(dialogo).getByRole('checkbox'))
    await usuario.click(confirmar)
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/public/revision-contraparte/aprobar', expect.objectContaining({
      method: 'POST', body: JSON.stringify({
        token: 'token-de-prueba', nombre_firmante: 'Claudia Pérez', cargo_firmante: 'Directora', firma,
      }),
    })))
    expect(await screen.findByRole('heading', { name: 'Revisión enviada correctamente.' })).toBeTruthy()
  })
})

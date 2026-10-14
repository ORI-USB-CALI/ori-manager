import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { RevisionContrapartePage } from './RevisionContrapartePage'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function preparar() {
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/17') ? {
      convenio_id: 41, codigo_convenio: 'CON-041', objeto: 'Cooperación académica',
      revision: { estado: 'PENDIENTE' },
      version_recibida: { numero: 3, contenido: { type: 'doc', content: [{ type: 'paragraph' }] } },
      enviada_por: { nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' },
      fecha_envio: '2026-10-01T14:00:00Z',
    } : {},
  ), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  const notify = vi.fn()
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={notify}>
        <MemoryRouter initialEntries={['/revisiones-contraparte/17']}>
          <Routes>
            <Route path="/revisiones-contraparte/:revisionId" element={<RevisionContrapartePage />} />
            <Route path="/revisiones-contraparte" element={<h1>Bandeja de contraparte</h1>} />
          </Routes>
        </MemoryRouter>
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { fetch, notify, usuario: userEvent.setup() }
}

describe('HT-03 revisión interna de contraparte', () => {
  it('aprueba la versión recibida sin exigir observaciones y vuelve a la bandeja', async () => {
    const { fetch, notify, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Aprobar elaboración' }))
    await usuario.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirmar aprobación' }))
    await screen.findByRole('heading', { name: 'Bandeja de contraparte' })
    expect(fetch).toHaveBeenCalledWith('/api/convenios/revisiones-contraparte/17/aprobar', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ expected_version: 3 }),
    }))
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }))
  })

  it.each(['', '  \n  '])('bloquea una devolución con observaciones vacías: %j', async (texto) => {
    const { fetch, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Devolver con observaciones' }))
    const campo = screen.getByRole('textbox', { name: 'Observaciones' }) as HTMLTextAreaElement
    expect(campo.required).toBe(true)
    expect(campo.getAttribute('aria-required')).toBe('true')
    expect(campo.getAttribute('aria-invalid')).toBe('false')
    expect(document.getElementById(campo.getAttribute('aria-describedby')!)?.textContent)
      .toBe('Debe existir al menos una observación para devolver el convenio.')
    await usuario.click(campo)
    if (texto) await usuario.type(campo, texto)
    await usuario.tab()
    expect(campo.getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByRole('alert').textContent).toContain('al menos una observación')
    const confirmar = screen.getByRole('button', { name: 'Confirmar devolución' }) as HTMLButtonElement
    expect(confirmar.disabled).toBe(true)
    await usuario.click(confirmar)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('corrige el error y devuelve únicamente la observación normalizada', async () => {
    const { fetch, usuario } = preparar()
    await usuario.click(await screen.findByRole('button', { name: 'Devolver con observaciones' }))
    const campo = screen.getByRole('textbox', { name: 'Observaciones' })
    await usuario.click(campo)
    await usuario.tab()
    expect(campo.getAttribute('aria-invalid')).toBe('true')
    await usuario.type(campo, '  Precisar las obligaciones de cada parte  ')
    expect(campo.getAttribute('aria-invalid')).toBe('false')
    expect(screen.queryByRole('alert')).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Confirmar devolución' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      '/api/convenios/revisiones-contraparte/17/devolver',
      expect.objectContaining({
        method: 'POST', body: JSON.stringify({ expected_version: 3, observaciones: ['Precisar las obligaciones de cada parte'] }),
      }),
    ))
    expect(await screen.findByRole('heading', { name: 'Bandeja de contraparte' })).toBeTruthy()
  })
})

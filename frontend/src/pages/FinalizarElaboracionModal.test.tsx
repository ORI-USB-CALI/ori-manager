import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { FinalizarElaboracionModal } from './FinalizarElaboracionModal'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function montar(tieneVersionFormal: boolean) {
  const onCerrar = vi.fn()
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cliente}>
      <NotificationsContext.Provider value={vi.fn()}>
        <FinalizarElaboracionModal
          convenioId={7}
          valores={{}}
          tieneVersionFormal={tieneVersionFormal}
          onFinalizado={() => Promise.resolve()}
          onErrorValidacion={() => {}}
          onCerrar={onCerrar}
        />
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
  return { onCerrar }
}

describe('FinalizarElaboracionModal (HT-15, Tarea 7: RN-01 a RN-03)', () => {
  it('impide cerrar durante el envío para no reabrir la edición antes de recibir el resultado', async () => {
    let resolver!: (respuesta: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { resolver = resolve })))
    const { onCerrar } = montar(false)
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar y enviar a Jurídica' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Cerrar' }) as HTMLButtonElement).disabled).toBe(true))
    const cancelar = new Event('cancel', { cancelable: true })
    fireEvent(screen.getByRole('dialog'), cancelar)
    expect(cancelar.defaultPrevented).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(onCerrar).not.toHaveBeenCalled()
    await act(async () => resolver(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })))
    await waitFor(() => expect(onCerrar).toHaveBeenCalledOnce())
  })
  it('en el primer envío explica que se crea la V1, no que se reutiliza', () => {
    montar(false)

    expect(screen.getByText(/se crea su versión formal 1 \(V1\)/)).toBeTruthy()
    expect(screen.queryByText(/se reutiliza esa versión/)).toBeNull()
  })

  it('en un reenvío explica que se reutiliza la versión si no cambió', () => {
    montar(true)

    expect(screen.getByText(/si no cambió desde la versión anterior, se reutiliza esa versión/)).toBeTruthy()
    expect(screen.queryByText(/se crea su versión formal 1/)).toBeNull()
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
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
          onCerrar={() => {}}
        />
      </NotificationsContext.Provider>
    </QueryClientProvider>,
  )
}

describe('FinalizarElaboracionModal (HT-15, Tarea 7: RN-01 a RN-03)', () => {
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

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { ExportarConvenioMenu } from '../components/ExportarConvenioMenu'
import { referenciaConvenio } from './epica02'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('referenciaConvenio (HT-06 FE-01, CA-01)', () => {
  it('muestra el código institucional cuando el convenio ya está formalizado', () => {
    expect(referenciaConvenio('USB-ORI-2026-00001', 41)).toBe('USB-ORI-2026-00001')
  })

  it('muestra una referencia provisional cuando todavía no hay código', () => {
    expect(referenciaConvenio(null, 41)).toBe('Convenio provisional #41')
  })

  it('trata un código vacío o en blanco como ausente', () => {
    expect(referenciaConvenio('', 41)).toBe('Convenio provisional #41')
    expect(referenciaConvenio('   ', 41)).toBe('Convenio provisional #41')
    expect(referenciaConvenio(undefined, 41)).toBe('Convenio provisional #41')
  })

  it('recorta los espacios del código oficial', () => {
    expect(referenciaConvenio('  USB-ORI-2026-00007  ', 41)).toBe('USB-ORI-2026-00007')
  })

  it('la referencia provisional no se confunde con un código institucional', () => {
    // CA-01: debe ser distinguible del código oficial aprobado.
    expect(referenciaConvenio(null, 41).startsWith('USB-ORI-')).toBe(false)
  })
})

function renderizarMenu(esBorrador: boolean) {
  return render(
    <NotificationsContext.Provider value={vi.fn()}>
      <ExportarConvenioMenu convenioId={41} esBorrador={esBorrador} />
    </NotificationsContext.Provider>,
  )
}

describe('ExportarConvenioMenu anuncia el modo real (HT-06 FE-01, CA-06, CA-07)', () => {
  it('antes de formalizar anuncia un documento de trabajo sin código ni firmas', () => {
    const { container } = renderizarMenu(true)
    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))

    expect(container.textContent).toContain('se generará como borrador')
    expect(container.textContent).toContain('sin código oficial ni firmas')
    // No debe prometer un documento oficial.
    expect(container.textContent).not.toContain('Documento oficial con membrete')
  })

  it('una vez formalizado anuncia el documento oficial', () => {
    const { container } = renderizarMenu(false)
    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))

    expect(container.textContent).toContain('Documento oficial con membrete y firmas')
    expect(container.textContent).not.toContain('se generará como borrador')
  })
})

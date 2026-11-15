import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { SeguimientoFirmasConvenio } from './SeguimientoFirmasConvenio'

const firma = {
  id: 17, orden: 1, rol_firmante: 'ADMINISTRADOR_ORI', parte: 'UNIVERSIDAD',
  nombre_firmante: 'Ana ORI', cargo_firmante: 'Administradora', correo_firmante: 'ana@example.com',
  modalidad: 'ELECTRONICA', estado: 'FIRMADA', fecha_firma: '2026-10-01T12:00:00Z',
  documento_id: null, documento: null, configurada: true, evidencia_electronica_disponible: true,
  invitaciones: [{ id: 1, estado: 'UTILIZADA' }],
}

function montar(firmas: object[] = [firma], estado = 'EN_CURSO', fallo?: number) {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/documentos/')) {
      return Promise.resolve(fallo ? {
        ok: false, status: fallo, text: async () => JSON.stringify({ detail: `Error ${fallo}` }),
      } : {
        ok: true, blob: async () => new Blob(['%PDF-1.4 original'], { type: 'application/pdf' }),
        headers: new Headers(),
      })
    }
    if (url.includes('/evidencia')) {
      return Promise.resolve(fallo ? {
        ok: false, status: fallo, text: async () => JSON.stringify({ detail: `Error ${fallo}` }),
      } : {
        ok: true, blob: async () => new Blob(['PNG original'], { type: 'image/png' }),
        headers: new Headers({ 'Content-Disposition': 'attachment; filename="firma.png"' }),
      })
    }
    return Promise.resolve({ ok: true, json: async () => ({ id: 5, estado, version_numero: 3, firmas }) })
  })
  vi.stubGlobal('fetch', fetchMock)
  const vista = render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <NotificationsContext.Provider value={vi.fn()}><SeguimientoFirmasConvenio convenioId={11} /></NotificationsContext.Provider>
  </QueryClientProvider></MemoryRouter>)
  return { ...vista, fetchMock }
}

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); this.dispatchEvent(new Event('close')) }
  window.URL.createObjectURL = vi.fn().mockReturnValue('blob:evidencia')
  window.URL.revokeObjectURL = vi.fn()
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('consulta de evidencia electrónica', () => {
  it('visualiza metadatos y PNG, conserva invitación y descarga autenticada; cierra y libera recursos', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const { fetchMock } = montar()
    const accion = await screen.findByRole('button', { name: 'Ver evidencia' })
    expect(screen.getByText('Utilizada')).toBeTruthy()
    await userEvent.click(accion)
    expect(await screen.findByRole('img', { name: 'Evidencia de firma electrónica' })).toBeTruthy()
    expect(screen.getAllByText('Ana ORI').length).toBe(2)
    await userEvent.click(screen.getByRole('button', { name: 'Descargar PNG' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(fetchMock).toHaveBeenCalledWith('/api/convenios/11/firmas/17/evidencia?disposicion=attachment', expect.objectContaining({ credentials: 'include', signal: expect.any(AbortSignal) }))
    const signal = fetchMock.mock.calls[1][1].signal as AbortSignal
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(signal.aborted).toBe(true)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:evidencia')
  })

  it.each([
    { ...firma, estado: 'PENDIENTE' },
    { ...firma, modalidad: 'FISICA' },
    { ...firma, evidencia_electronica_disponible: false },
  ])('oculta la acción cuando no corresponde', async (datos) => {
    montar([datos])
    await screen.findByText('Ana ORI')
    expect(screen.queryByRole('button', { name: 'Ver evidencia' })).toBeNull()
  })

  it('usa botones uniformes y abre el PDF original en el visor con descarga y cierre', async () => {
    const { fetchMock } = montar([
      firma,
      { ...firma, id: 18, modalidad: 'FISICA', documento: { id: 4, nombre_archivo: 'soporte.pdf', tipo_mime: 'application/pdf' } },
    ])
    const acciones = await screen.findAllByRole('button', { name: 'Ver evidencia' })
    expect(acciones).toHaveLength(2)
    expect(acciones[0].className).toBe(acciones[1].className)
    expect(acciones[0].parentElement?.className).toBe(acciones[1].parentElement?.className)
    expect(screen.getByText('soporte.pdf')).toBeTruthy()
    expect(screen.queryByRole('link', { name: /Ver\/descargar/ })).toBeNull()
    await userEvent.click(acciones[1])
    expect(await screen.findByTestId('preview-iframe')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'soporte.pdf' })).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith('/api/convenios/11/documentos/4/contenido?disposicion=inline', expect.objectContaining({ credentials: 'include', signal: expect.any(AbortSignal) }))
    const descarga = screen.getByRole('link', { name: 'Descargar PDF' })
    expect(descarga.getAttribute('href')).toBe('/api/convenios/11/documentos/4/contenido?disposicion=attachment')
    expect(descarga.getAttribute('download')).toBe('soporte.pdf')
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:evidencia')
  })

  it.each([403, 404])('maneja HTTP %s al abrir evidencia física', async (codigo) => {
    montar([{ ...firma, modalidad: 'FISICA', documento: { id: 4, nombre_archivo: 'soporte.pdf', tipo_mime: 'application/pdf' } }], 'COMPLETADO', codigo)
    await userEvent.click(await screen.findByRole('button', { name: 'Ver evidencia' }))
    expect(await screen.findByTestId('preview-error')).toBeTruthy()
    expect(screen.queryByTestId('preview-iframe')).toBeNull()
  })

  it.each([401, 403, 404, 409, 502])('maneja HTTP %s y permite cerrar', async (codigo) => {
    montar([firma], 'COMPLETADO', codigo)
    await userEvent.click(await screen.findByRole('button', { name: 'Ver evidencia' }))
    expect(await screen.findByTestId('preview-error')).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('aborta al desmontar mientras carga', async () => {
    const { unmount, fetchMock } = montar()
    await screen.findByRole('button', { name: 'Ver evidencia' })
    fetchMock.mockImplementationOnce(() => new Promise(() => {}))
    await userEvent.click(screen.getByRole('button', { name: 'Ver evidencia' }))
    expect(screen.getByTestId('preview-cargando')).toBeTruthy()
    const signal = fetchMock.mock.calls[1][1].signal as AbortSignal
    unmount()
    expect(signal.aborted).toBe(true)
  })

  it('maneja un permiso revocado al descargar', async () => {
    const { fetchMock } = montar()
    await userEvent.click(await screen.findByRole('button', { name: 'Ver evidencia' }))
    await screen.findByRole('img')
    fetchMock.mockResolvedValueOnce({ ok: false, status: 403, text: async () => JSON.stringify({ detail: 'Acceso denegado' }) })
    await userEvent.click(screen.getByRole('button', { name: 'Descargar PNG' }))
    expect(await screen.findByText('Acceso denegado')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Descargar PNG' })).toBeNull()
  })

  it('conserva la confirmación de formalización con siete firmas', async () => {
    montar(Array.from({ length: 7 }, (_, i) => ({ ...firma, id: i + 1, orden: i + 1 })))
    await userEvent.click(await screen.findByRole('button', { name: 'Formalizar convenio' }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('Se cerrará el proceso de firmas de la versión 3.')).toBeTruthy()
  })
})

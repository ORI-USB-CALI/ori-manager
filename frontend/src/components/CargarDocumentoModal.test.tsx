import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { CargarDocumentoModal } from './CargarDocumentoModal'

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

describe('CargarDocumentoModal (CA-01, CA-02)', () => {
  it('muestra la alerta de validación en cliente cuando se selecciona un archivo que no es PDF', async () => {
    const notify = vi.fn()
    render(
      <NotificationsContext.Provider value={notify}>
        <CargarDocumentoModal convenioId={10} onCerrar={() => {}} />
      </NotificationsContext.Provider>,
    )

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(fileInput).not.toBeNull()

    const txtFile = new File(['texto plano'], 'documento.txt', { type: 'text/plain' })
    fireEvent.change(fileInput, { target: { files: [txtFile] } })

    expect(
      screen.getByText('Solo se permiten documentos en formato PDF'),
    ).toBeTruthy()
    const botonSubir = screen.getByRole('button', { name: /subir documento pdf/i }) as HTMLButtonElement
    expect(botonSubir.disabled).toBe(true)
  })

  it('permite seleccionar un PDF válido y realizar la carga exitosa', async () => {
    const notify = vi.fn()
    const onCerrar = vi.fn()
    const onDocumentoCargado = vi.fn()

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: 1,
        nombre_archivo: 'convenio_soporte.pdf',
        tipo_mime: 'application/pdf',
        tamano_bytes: 1024,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <NotificationsContext.Provider value={notify}>
        <CargarDocumentoModal
          convenioId={10}
          onCerrar={onCerrar}
          onDocumentoCargado={onDocumentoCargado}
        />
      </NotificationsContext.Provider>,
    )

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const pdfFile = new File(['%PDF-1.4 contenido'], 'convenio_soporte.pdf', {
      type: 'application/pdf',
    })

    fireEvent.change(fileInput, { target: { files: [pdfFile] } })

    expect(screen.getByText(/convenio_soporte\.pdf/)).toBeTruthy()
    const botonSubir = screen.getByRole('button', { name: /subir documento pdf/i }) as HTMLButtonElement
    expect(botonSubir.disabled).toBe(false)

    await userEvent.click(botonSubir)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/convenios/10/documentos',
        expect.objectContaining({
          method: 'POST',
        }),
      )
      expect(notify).toHaveBeenCalledWith({
        type: 'success',
        message: 'Documento cargado correctamente',
      })
      expect(onDocumentoCargado).toHaveBeenCalled()
      expect(onCerrar).toHaveBeenCalled()
    })
  })
})

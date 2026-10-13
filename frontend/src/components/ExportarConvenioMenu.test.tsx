import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import { ExportarConvenioMenu } from './ExportarConvenioMenu'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
  window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
  window.URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function renderizarMenu(convenioId = 42, esBorrador = false) {
  const notify = vi.fn()
  const renderResult = render(
    <NotificationsContext.Provider value={notify}>
      <ExportarConvenioMenu convenioId={convenioId} esBorrador={esBorrador} />
    </NotificationsContext.Provider>,
  )
  return { ...renderResult, notify }
}

describe('ExportarConvenioMenu (FE-01, FE-03, CA-01, CA-03)', () => {
  it('renderiza el botón principal de exportación cerrado inicialmente', () => {
    renderizarMenu()

    const boton = screen.getByRole('button', { name: /exportar o generar documento/i })
    expect(boton).toBeTruthy()
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('abre el menú desplegable con opciones PDF y Excel al hacer clic', () => {
    renderizarMenu()

    const boton = screen.getByRole('button', { name: /exportar o generar documento/i })
    fireEvent.click(boton)

    expect(boton.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('menu')).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: /exportar como pdf/i })).toBeTruthy()
    expect(screen.getByRole('menuitem', { name: /exportar como excel/i })).toBeTruthy()
  })

  it('inicia descarga en PDF, bloquea clics concurrentes y notifica éxito (FE-01, CA-01)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({
        'Content-Disposition': 'attachment; filename="Convenio_CONV-001_2026-10-12.pdf"',
      }),
      blob: () => Promise.resolve(new Blob(['%PDF-fake'], { type: 'application/pdf' })),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { notify } = renderizarMenu(10)

    const botonPrincipal = screen.getByRole('button', { name: /exportar o generar documento/i }) as HTMLButtonElement
    fireEvent.click(botonPrincipal)

    const opcionPdf = screen.getByRole('menuitem', { name: /exportar como pdf/i })
    fireEvent.click(opcionPdf)

    // Se deshabilita durante la descarga y muestra estado de carga
    expect(botonPrincipal.disabled).toBe(true)
    expect(screen.getByText(/generando pdf…/i)).toBeTruthy()

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/convenios/10/exportar?formato=pdf',
        { credentials: 'include' },
      )
    })

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'success',
          message: 'Documento generado y descargado correctamente',
        }),
      )
    })

    // Se reactiva al terminar
    await waitFor(() => {
      expect(botonPrincipal.disabled).toBe(false)
    })
  })

  it('inicia descarga en Excel correctamente cuando se selecciona la opción (FE-01)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({
        'Content-Disposition': 'attachment; filename="Convenio_CONV-001_2026-10-12.xlsx"',
      }),
      blob: () => Promise.resolve(new Blob(['PK-fake'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { notify } = renderizarMenu(10)

    const botonPrincipal = screen.getByRole('button', { name: /exportar o generar documento/i })
    fireEvent.click(botonPrincipal)

    const opcionExcel = screen.getByRole('menuitem', { name: /exportar como excel/i })
    fireEvent.click(opcionExcel)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/convenios/10/exportar?formato=excel',
        { credentials: 'include' },
      )
    })

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'success',
          message: 'Documento generado y descargado correctamente',
        }),
      )
    })
  })

  it('intercepta error 422 y despliega el modal de datos incompletos con viñetas (FE-03, CA-03)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: () =>
        Promise.resolve(
          JSON.stringify({
            detail: {
              message: 'El convenio no cuenta con información suficiente',
              faltantes: ['objeto', 'tipo_convenio'],
            },
          }),
        ),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { notify } = renderizarMenu(15)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /exportar como pdf/i }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy()
    })

    // Título exacto requerido por FE-03
    expect(screen.getByText('No se puede generar el documento')).toBeTruthy()

    // Mensaje explicativo requerido por FE-03
    expect(
      screen.getByText(
        /El convenio no cuenta con la información requerida para emitir un documento oficial/i,
      ),
    ).toBeTruthy()

    // Lista con viñetas de los campos pendientes
    expect(screen.getByText('Objeto del convenio')).toBeTruthy()
    expect(screen.getByText('Tipo de convenio')).toBeTruthy()

    // No debe disparar notificación de error genérica cuando abre el modal específico
    expect(notify).not.toHaveBeenCalledWith(expect.objectContaining({ type: 'error' }))

    // Cerrar el modal con el botón Entendido
    const botonEntendido = screen.getByRole('button', { name: /entendido/i })
    fireEvent.click(botonEntendido)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  it('abre el modal con el 422 de nivel superior de HU-24 (campos_faltantes)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: () =>
        Promise.resolve(
          JSON.stringify({
            error: 'CONVENIO_INCOMPLETO',
            message: 'No es posible generar el documento oficial. Faltan datos obligatorios.',
            campos_faltantes: ['objeto', 'fecha_fin_vigencia'],
          }),
        ),
    }))

    const { notify } = renderizarMenu(15)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /exportar como excel/i }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy()
    })
    expect(screen.getByText('Objeto del convenio')).toBeTruthy()
    expect(screen.getByText('Fecha de fin de vigencia')).toBeTruthy()
    expect(notify).not.toHaveBeenCalledWith(expect.objectContaining({ type: 'error' }))
  })

  it('aclara que el documento será un borrador cuando el convenio está en elaboración', () => {
    renderizarMenu(20, true)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))

    expect(
      screen.getByText('El documento se generará como borrador, sin formalización ni firmas.'),
    ).toBeTruthy()
    // Conserva las dos opciones, sin selector entre borrador y oficial.
    expect(screen.getAllByRole('menuitem')).toHaveLength(2)
  })

  it('no muestra la aclaración de borrador fuera de elaboración', () => {
    renderizarMenu(20, false)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))

    expect(screen.queryByText(/se generará como borrador/i)).toBeNull()
  })

  it('el modal de un borrador incompleto lista solo lo que pide el borrador', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: () =>
        Promise.resolve(
          JSON.stringify({
            error: 'CONVENIO_INCOMPLETO',
            message: 'No es posible generar el documento oficial. Faltan datos obligatorios.',
            campos_faltantes: ['entidad_participante', 'version_contractual', 'clausulas'],
          }),
        ),
    }))

    renderizarMenu(21, true)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /exportar como pdf/i }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy()
    })
    expect(screen.getByText(/para generar el borrador/i)).toBeTruthy()
    expect(screen.getByText('Entidad participante (aliado)')).toBeTruthy()
    expect(screen.getByText('Versión contractual actual')).toBeTruthy()
    expect(screen.getByText('Contenido contractual (cláusulas)')).toBeTruthy()
    // No exige firmas ni vigencia que el borrador no requiere.
    expect(screen.queryByText(/representante legal/i)).toBeNull()
    expect(screen.queryByText(/vigencia/i)).toBeNull()
    expect(screen.queryByText(/documento oficial/i)).toBeNull()
  })

  it('notifica error 403 cuando el usuario no tiene permisos', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      text: () => Promise.resolve(JSON.stringify({ detail: 'No autorizado' })),
    })
    vi.stubGlobal('fetch', fetchMock)

    const { notify } = renderizarMenu(15)

    fireEvent.click(screen.getByRole('button', { name: /exportar o generar documento/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /exportar como pdf/i }))

    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          message: expect.stringMatching(/permiso/i),
        }),
      )
    })
  })
})

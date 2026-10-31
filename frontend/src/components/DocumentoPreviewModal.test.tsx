import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { DocumentoPreviewModal } from './DocumentoPreviewModal'

describe('DocumentoPreviewModal (HU-23: CA-01, CA-02, CA-03, CA-04, CA-06, CA-07, CA-08)', () => {
  const onCerrar = vi.fn()
  const mockCreateObjectURL = vi.fn()
  const mockRevokeObjectURL = vi.fn()

  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '')
    }
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute('open')
      this.dispatchEvent(new Event('close'))
    }
  })

  beforeEach(() => {
    onCerrar.mockClear()
    mockCreateObjectURL.mockReset().mockReturnValue('blob:http://localhost/mock-preview-uuid')
    mockRevokeObjectURL.mockReset()
    window.URL.createObjectURL = mockCreateObjectURL
    window.URL.revokeObjectURL = mockRevokeObjectURL
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('muestra estado de carga inicial y luego renderiza el iframe del PDF (CA-01, CA-02)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4 prueba'], { type: 'application/pdf' }),
        headers: new Headers({
          'Content-Type': 'application/pdf',
          'Content-Disposition': "inline; filename*=UTF-8''convenio.pdf",
        }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="convenio.pdf"
        urlContenido="/convenios/10/documentos/1/contenido?disposicion=inline"
        urlDescarga="/api/convenios/10/documentos/1/contenido?disposicion=attachment"
        tipoMime="application/pdf"
        onCerrar={onCerrar}
      />,
    )

    // Título con el nombre del documento
    expect(screen.getByRole('heading', { level: 2, name: 'convenio.pdf' })).toBeTruthy()

    // Estado cargando inicial
    expect(screen.getByTestId('preview-cargando')).toBeTruthy()

    // Carga finalizada con iframe
    await waitFor(() => {
      expect(screen.queryByTestId('preview-cargando')).toBeNull()
      const iframe = screen.getByTestId('preview-iframe') as HTMLIFrameElement
      expect(iframe).toBeTruthy()
      expect(iframe.getAttribute('src')).toBe('blob:http://localhost/mock-preview-uuid')
      expect(iframe.getAttribute('title')).toBe('Previsualización de convenio.pdf')
    })

    // Enlace de descarga disponible
    const btnDescargar = screen.getByRole('link', { name: 'Descargar' }) as HTMLAnchorElement
    expect(btnDescargar.getAttribute('href')).toBe('/api/convenios/10/documentos/1/contenido?disposicion=attachment')
    expect(btnDescargar.getAttribute('download')).toBe('convenio.pdf')
  })

  it('invoca onCerrar al hacer clic en el botón de cerrar (CA-03, CA-08)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4 prueba'], { type: 'application/pdf' }),
        headers: new Headers(),
      }),
    )

    const user = userEvent.setup()

    render(
      <DocumentoPreviewModal
        nombreArchivo="soporte.pdf"
        urlContenido="/convenios/10/documentos/1/descargar?disposicion=inline"
        onCerrar={onCerrar}
      />,
    )

    const btnCerrarIcono = screen.getByRole('button', { name: 'Cerrar previsualizador' })
    await user.click(btnCerrarIcono)

    expect(onCerrar).toHaveBeenCalledTimes(1)
  })

  it('restaura el foco en el elemento activador al cerrarse (CA-08)', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: new Headers(),
      }),
    )

    // Crear un botón en el documento que simule el activador
    const botonActivador = document.createElement('button')
    botonActivador.textContent = 'Ver documento'
    document.body.appendChild(botonActivador)
    botonActivador.focus()
    expect(document.activeElement).toBe(botonActivador)

    const { unmount } = render(
      <DocumentoPreviewModal
        nombreArchivo="soporte.pdf"
        urlContenido="/convenios/10/documentos/1/descargar?disposicion=inline"
        onCerrar={onCerrar}
      />,
    )

    unmount()
    expect(document.activeElement).toBe(botonActivador)
    document.body.removeChild(botonActivador)
  })

  it('informa formato no compatible cuando el archivo no es PDF y permite descarga (CA-06, RN-01, RN-08)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="anexo_tecnico.xlsx"
        urlContenido="/solicitudes/recibidas/5/documentos/2/contenido?disposicion=inline"
        urlDescarga="/api/solicitudes/recibidas/5/documentos/2/contenido?disposicion=attachment"
        tipoMime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onCerrar={onCerrar}
      />,
    )

    // No debe intentar fetch de previsualización para formatos no PDF
    expect(fetchMock).not.toHaveBeenCalled()

    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
    expect(screen.getByText('Formato no compatible con el visor')).toBeTruthy()
    expect(
      screen.getByText(/Actualmente solo se admite la previsualización de archivos PDF/i),
    ).toBeTruthy()

    // Botón para descarga directa
    const btnDescargar = screen.getByRole('link', { name: 'Descargar archivo' }) as HTMLAnchorElement
    expect(btnDescargar.getAttribute('href')).toBe('/api/solicitudes/recibidas/5/documentos/2/contenido?disposicion=attachment')
    expect(btnDescargar.getAttribute('download')).toBe('anexo_tecnico.xlsx')
  })

  it('maneja error 404 cuando el documento no existe o no está vigente (CA-07)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => JSON.stringify({ detail: 'Documento no encontrado' }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="eliminado.pdf"
        urlContenido="/convenios/10/documentos/999/contenido?disposicion=inline"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
      expect(screen.getByText('El documento solicitado no fue encontrado o no está vigente.')).toBeTruthy()
    })
  })

  it('maneja error 403 de permisos insuficientes (CA-05, CA-07)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        text: async () => JSON.stringify({ detail: 'No tiene permiso para esta operación' }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="restringido.pdf"
        urlContenido="/solicitudes/recibidas/5/documentos/1/contenido?disposicion=inline"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
      expect(screen.getByText('No tiene permiso para consultar este documento.')).toBeTruthy()
    })
  })

  it('maneja error 502 de almacenamiento y permite reintentar (CA-07)', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        text: async () => JSON.stringify({ detail: 'No fue posible recuperar el documento almacenado' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4 recuperado'], { type: 'application/pdf' }),
        headers: new Headers(),
      })

    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="respaldo.pdf"
        urlContenido="/convenios/10/documentos/1/descargar?disposicion=inline"
        onCerrar={onCerrar}
      />,
    )

    // Esperar primer intento fallido
    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
      expect(screen.getByText('No fue posible recuperar el documento almacenado')).toBeTruthy()
    })

    // Hacer clic en Reintentar
    const btnReintentar = screen.getByRole('button', { name: 'Reintentar' })
    fireEvent.click(btnReintentar)

    // Debe mostrar cargando y luego el iframe
    await waitFor(() => {
      expect(screen.queryByTestId('preview-error')).toBeNull()
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('libera la URL del objeto blob al desmontarse para evitar fugas de memoria', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: new Headers(),
      }),
    )

    const { unmount } = render(
      <DocumentoPreviewModal
        nombreArchivo="test.pdf"
        urlContenido="/convenios/1/documentos/1/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })

    unmount()

    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:http://localhost/mock-preview-uuid')
  })

  it('maneja error 401 de sesión expirada (CA-07)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        text: async () => JSON.stringify({ detail: 'No autenticado' }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="convenio_confidencial.pdf"
        urlContenido="/convenios/10/documentos/5/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
      expect(screen.getByText('Sesión expirada o no autenticada. Por favor inicie sesión nuevamente.')).toBeTruthy()
    })
  })

  it('no muestra botones ni enlaces de descarga si puedeDescargar es false (CA-04, CA-05)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: new Headers(),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="restringido.pdf"
        urlContenido="/convenios/10/documentos/1/contenido"
        puedeDescargar={false}
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })

    expect(screen.queryByRole('link', { name: 'Descargar' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Descargar archivo' })).toBeNull()
  })

  it('invoca onCerrar al disparar el evento cancel del diálogo (Escape) (CA-03, CA-08)', () => {
    const { container } = render(
      <DocumentoPreviewModal
        nombreArchivo="documento.pdf"
        urlContenido="/convenios/10/documentos/1/contenido"
        onCerrar={onCerrar}
      />,
    )

    const dialog = container.querySelector('dialog') as HTMLDialogElement
    expect(dialog).toBeTruthy()

    fireEvent(dialog, new Event('cancel'))
    expect(onCerrar).toHaveBeenCalled()
  })

  it('maneja fallas de red mostrando mensaje de error y permitiendo reintento (CA-07)', async () => {
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error('Fallo de conexión a la red'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: new Headers(),
      })

    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="red.pdf"
        urlContenido="/convenios/10/documentos/1/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
      expect(screen.getByText('Fallo de conexión a la red')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    await waitFor(() => {
      expect(screen.queryByTestId('preview-error')).toBeNull()
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('soporta extensión en mayúsculas (.PDF) y detecta por tipo MIME (RN-01)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: new Headers(),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="ANEXO_MAYUSCULA.PDF"
        urlContenido="/convenios/10/documentos/1/contenido"
        tipoMime="application/pdf"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })
  })
})


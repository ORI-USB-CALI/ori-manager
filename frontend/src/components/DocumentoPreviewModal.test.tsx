/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { URL as NodeURL } from 'node:url'

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { DocumentoPreviewModal } from './DocumentoPreviewModal'

function diferido<T>() {
  let resolver!: (valor: T) => void
  let rechazar!: (error: Error) => void
  const promesa = new Promise<T>((resolve, reject) => {
    resolver = resolve
    rechazar = reject
  })
  return { promesa, resolver, rechazar }
}

function respuestaPdf(blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })) {
  return { ok: true, status: 200, blob: async () => blob, headers: new Headers() }
}

describe('DocumentoPreviewModal (HU-23: CA-01, CA-02, CA-03, CA-04, CA-06, CA-07, CA-08)', () => {
  const onCerrar = vi.fn()
  const mockCreateObjectURL = vi.fn()
  const mockRevokeObjectURL = vi.fn()

  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute('open', '')
      this.querySelector('button')?.focus()
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
      expect(screen.getByText('No fue posible recuperar el documento almacenado. Intente nuevamente.')).toBeTruthy()
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
      expect(screen.getByText(/Compruebe su conexión/)).toBeTruthy()
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

  it('informa formato no compatible cuando el nombre es .pdf pero el tipo MIME es image/png (H-01)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="captura_falsa.pdf"
        urlContenido="/convenios/10/documentos/1/contenido"
        tipoMime="image/png"
        puedeDescargar={true}
        onCerrar={onCerrar}
      />,
    )

    // No debe intentar fetch de previsualización porque el MIME no es PDF
    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
    expect(screen.queryByTestId('preview-iframe')).toBeNull()
    expect(screen.getByRole('link', { name: 'Descargar archivo' })).toBeTruthy()
  })

  it('informa formato no compatible cuando el nombre es .pdf pero el tipo MIME es image/jpeg (H-01)', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="foto.pdf"
        urlContenido="/convenios/10/documentos/2/contenido"
        tipoMime="image/jpeg"
        puedeDescargar={true}
        onCerrar={onCerrar}
      />,
    )

    expect(fetchMock).not.toHaveBeenCalled()
    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
    expect(screen.queryByTestId('preview-iframe')).toBeNull()
  })

  it('no renderiza en iframe si la respuesta autenticada devuelve text/html en lugar de PDF (H-01)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['<!DOCTYPE html><html><body>Error</body></html>'], { type: 'text/html' }),
        headers: new Headers({ 'Content-Type': 'text/html' }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="documento.pdf"
        urlContenido="/convenios/10/documentos/3/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.queryByTestId('preview-cargando')).toBeNull()
    })

    expect(screen.queryByTestId('preview-iframe')).toBeNull()
    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
  })

  it('no renderiza en iframe si el contenido no tiene la firma mágica %PDF- (H-01)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        blob: async () => new Blob(['CONTENIDO CORRUPTO NO PDF'], { type: 'application/pdf' }),
        headers: new Headers({ 'Content-Type': 'application/pdf' }),
      }),
    )

    render(
      <DocumentoPreviewModal
        nombreArchivo="corrupto.pdf"
        urlContenido="/convenios/10/documentos/4/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.queryByTestId('preview-cargando')).toBeNull()
    })

    expect(screen.queryByTestId('preview-iframe')).toBeNull()
    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
  })

  it('no muestra opción de descarga en formato incompatible si puedeDescargar es false (H-01)', async () => {
    render(
      <DocumentoPreviewModal
        nombreArchivo="archivo.xlsx"
        urlContenido="/convenios/10/documentos/5/contenido"
        tipoMime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        puedeDescargar={false}
        onCerrar={onCerrar}
      />,
    )

    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Descargar archivo' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Descargar' })).toBeNull()
  })

  it.each([401, 403])('oculta todas las descargas y el reintento tras %i', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status, statusText: 'Acceso denegado',
      text: async () => JSON.stringify({ detail: 'información interna del almacenamiento' }),
    }))
    render(<DocumentoPreviewModal nombreArchivo="privado.pdf" urlContenido="/documento" onCerrar={onCerrar} />)
    await screen.findByTestId('preview-error')
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull()
    expect(screen.queryByText(/información interna/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeTruthy()
  })

  it.each([404, 502, 500])('conserva descarga autenticada y reintento tras un error recuperable %i', async (status) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false, status, statusText: 'ruta interna secreta',
      text: async () => JSON.stringify({ detail: 'ruta interna secreta' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/api/documento?disposicion=inline" onCerrar={onCerrar} />)
    await screen.findByTestId('preview-error')
    expect(screen.queryByText(/ruta interna secreta/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Descargar' }).getAttribute('href'))
      .toBe('/api/documento?disposicion=attachment')
    expect(fetchMock).toHaveBeenCalledWith('/api/documento?disposicion=inline', {
      credentials: 'include', signal: expect.any(AbortSignal),
    })
  })

  it.each(['cerrar', 'desmontar'])('cancela al %s durante una petición pendiente, incluso si fetch ignora AbortSignal', async (accion) => {
    const pendiente = diferido<ReturnType<typeof respuestaPdf>>()
    const fetchMock = vi.fn().mockReturnValue(pendiente.promesa)
    vi.stubGlobal('fetch', fetchMock)
    const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/documento" onCerrar={onCerrar} />)
    const signal = fetchMock.mock.calls[0][1].signal as AbortSignal
    if (accion === 'cerrar') fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    else vista.unmount()
    expect(signal.aborted).toBe(true)
    await act(async () => { pendiente.resolver(respuestaPdf()); await pendiente.promesa })
    expect(mockCreateObjectURL).not.toHaveBeenCalled()
    expect(mockRevokeObjectURL).not.toHaveBeenCalled()
  })

  it.each([
    ['cerrar', false], ['desmontar', false], ['cerrar', true], ['desmontar', true],
  ])('no crea recursos al %s durante Blob.text() (rechazo: %s)', async (accion, falla) => {
    const texto = diferido<string>()
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    const leer = vi.fn().mockReturnValue(texto.promesa)
    vi.spyOn(blob, 'slice').mockReturnValue({ text: leer } as unknown as Blob)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respuestaPdf(blob)))
    const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/documento" onCerrar={onCerrar} />)
    await waitFor(() => expect(leer).toHaveBeenCalledTimes(1))
    if (accion === 'cerrar') fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    else vista.unmount()
    await act(async () => {
      if (falla) texto.rechazar(new Error('falló Blob.text'))
      else texto.resolver('%PDF-')
      await texto.promesa.catch(() => undefined)
    })
    expect(mockCreateObjectURL).not.toHaveBeenCalled()
    expect(mockRevokeObjectURL).not.toHaveBeenCalled()
  })

  it('ignora una respuesta HTTP antigua que llega después del documento nuevo', async () => {
    const antigua = diferido<ReturnType<typeof respuestaPdf>>()
    const nuevoBlob = new Blob(['%PDF-1.7 nuevo'], { type: 'application/pdf' })
    const fetchMock = vi.fn().mockReturnValueOnce(antigua.promesa).mockResolvedValueOnce(respuestaPdf(nuevoBlob))
    vi.stubGlobal('fetch', fetchMock)
    const vista = render(<DocumentoPreviewModal nombreArchivo="antes.pdf" urlContenido="/antes" onCerrar={onCerrar} />)
    const signalAntigua = fetchMock.mock.calls[0][1].signal as AbortSignal
    vista.rerender(<DocumentoPreviewModal nombreArchivo="nuevo.pdf" urlContenido="/nuevo" onCerrar={onCerrar} />)
    await screen.findByTitle('Previsualización de nuevo.pdf')
    expect(signalAntigua.aborted).toBe(true)
    await act(async () => { antigua.resolver(respuestaPdf()); await antigua.promesa })
    expect(mockCreateObjectURL).toHaveBeenCalledExactlyOnceWith(nuevoBlob)
  })

  it('una validación antigua no sobrescribe un reintento más reciente', async () => {
    const textoAntiguo = diferido<string>()
    const antiguoBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    const leer = vi.fn().mockReturnValue(textoAntiguo.promesa)
    vi.spyOn(antiguoBlob, 'slice').mockReturnValue({ text: leer } as unknown as Blob)
    const nuevoBlob = new Blob(['%PDF-1.7 nuevo'], { type: 'application/pdf' })
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(respuestaPdf(antiguoBlob))
      .mockRejectedValueOnce(new Error('red'))
      .mockResolvedValueOnce(respuestaPdf(nuevoBlob)))
    const vista = render(<DocumentoPreviewModal nombreArchivo="antes.pdf" urlContenido="/antes" onCerrar={onCerrar} />)
    await waitFor(() => expect(leer).toHaveBeenCalled())
    vista.rerender(<DocumentoPreviewModal nombreArchivo="nuevo.pdf" urlContenido="/nuevo" onCerrar={onCerrar} />)
    await screen.findByTestId('preview-error')
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await screen.findByTitle('Previsualización de nuevo.pdf')
    await act(async () => { textoAntiguo.resolver('HTML!'); await textoAntiguo.promesa })
    expect(mockCreateObjectURL).toHaveBeenCalledExactlyOnceWith(nuevoBlob)
    expect(screen.queryByTestId('preview-no-compatible')).toBeNull()
    expect(screen.queryByTestId('preview-error')).toBeNull()
    expect(screen.getByTitle('Previsualización de nuevo.pdf')).toBeTruthy()
  })

  it('revoca la URL anterior al cambiar de documento y al cerrar sin desmontar', async () => {
    mockCreateObjectURL.mockReturnValueOnce('blob:primero').mockReturnValueOnce('blob:segundo')
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => respuestaPdf()))
    const vista = render(<DocumentoPreviewModal nombreArchivo="uno.pdf" urlContenido="/uno" onCerrar={onCerrar} />)
    await screen.findByTestId('preview-iframe')
    vista.rerender(<DocumentoPreviewModal nombreArchivo="dos.pdf" urlContenido="/dos" onCerrar={onCerrar} />)
    await waitFor(() => expect(screen.getByTestId('preview-iframe').getAttribute('src')).toBe('blob:segundo'))
    expect(mockRevokeObjectURL).toHaveBeenCalledExactlyOnceWith('blob:primero')
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(mockRevokeObjectURL.mock.calls).toEqual([['blob:primero'], ['blob:segundo']])
    expect(screen.queryByRole('dialog')).toBeNull()
    vista.unmount()
    expect(mockRevokeObjectURL).toHaveBeenCalledTimes(2)
  })

  it('libera una sola URL en cada apertura y cierre consecutivo', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => respuestaPdf()))
    for (let i = 1; i <= 3; i++) {
      mockCreateObjectURL.mockReturnValueOnce(`blob:${i}`)
      const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/documento" onCerrar={onCerrar} />)
      await screen.findByTestId('preview-iframe')
      expect(mockCreateObjectURL).toHaveBeenCalledTimes(i)
      expect(mockRevokeObjectURL).toHaveBeenCalledTimes(i - 1)
      fireEvent.click(screen.getByRole('button', { name: 'Cerrar previsualizador' }))
      vista.unmount()
      expect(mockRevokeObjectURL).toHaveBeenCalledTimes(i)
      expect(onCerrar).toHaveBeenCalledTimes(i)
    }
  })

  it('reinicia los estados y libera recursos al cambiar de PDF a formato incompatible', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaPdf())
    vi.stubGlobal('fetch', fetchMock)
    const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/pdf" onCerrar={onCerrar} />)
    await screen.findByTestId('preview-iframe')
    vista.rerender(<DocumentoPreviewModal nombreArchivo="imagen.png" tipoMime="image/png" urlContenido="/png" onCerrar={onCerrar} />)
    expect(screen.getByTestId('preview-no-compatible')).toBeTruthy()
    expect(screen.queryByTestId('preview-iframe')).toBeNull()
    expect(mockRevokeObjectURL).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('tiene nombre accesible, foco inicial, navegación por teclado y un único aviso al cancelar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    const activador = document.createElement('button')
    document.body.appendChild(activador)
    activador.focus()
    try {
      render(<DocumentoPreviewModal nombreArchivo="accesible.pdf" urlContenido="/pdf" onCerrar={onCerrar} />)
      const dialog = screen.getByRole('dialog', { name: 'accesible.pdf' })
      expect(dialog.getAttribute('aria-modal')).toBe('true')
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cerrar previsualizador' }))
      const user = userEvent.setup()
      await user.tab()
      expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Descargar' }))
      await user.tab()
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cerrar' }))
      fireEvent(dialog, new Event('cancel', { cancelable: true }))
      fireEvent(dialog, new Event('close'))
      expect(onCerrar).toHaveBeenCalledTimes(1)
      expect(dialog.hasAttribute('open')).toBe(false)
      expect(screen.queryByRole('dialog')).toBeNull()
      expect(document.activeElement).toBe(activador)
    } finally {
      activador.remove()
    }
  })

  it('permite cerrar cuando el activador ya no existe', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    const activador = document.createElement('button')
    document.body.appendChild(activador)
    activador.focus()
    const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/pdf" onCerrar={onCerrar} />)
    activador.remove()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    vista.unmount()
    expect(onCerrar).toHaveBeenCalledTimes(1)
  })

  it('los estilos reales mantienen el diálogo cerrado oculto aunque el padre no lo desmonte', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
    const estilo = document.createElement('style')
    // JSDOM no carga el @import de variables; las reglas de distribución son las reales.
    estilo.textContent = readFileSync(new NodeURL('../index.css', import.meta.url), 'utf8')
      .replace(/^@import[^;]*;/gm, '')
    document.head.appendChild(estilo)
    try {
      const vista = render(<DocumentoPreviewModal nombreArchivo="archivo.pdf" urlContenido="/pdf" onCerrar={onCerrar} />)
      const dialog = screen.getByRole('dialog')
      expect(getComputedStyle(dialog).display).toBe('flex')
      fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
      expect(getComputedStyle(dialog).display).toBe('none')
      vista.unmount()
    } finally {
      estilo.remove()
    }
  })

  it('limpia cualquier previsualización anterior inválida al reintentar después de un error', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        text: async () => JSON.stringify({ detail: 'Falla temporal' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        blob: async () => new Blob(['%PDF-1.4 valido'], { type: 'application/pdf' }),
        headers: new Headers(),
      })

    vi.stubGlobal('fetch', fetchMock)

    render(
      <DocumentoPreviewModal
        nombreArchivo="reintento.pdf"
        urlContenido="/convenios/10/documentos/6/contenido"
        onCerrar={onCerrar}
      />,
    )

    await waitFor(() => {
      expect(screen.getByTestId('preview-error')).toBeTruthy()
    })
    expect(screen.queryByTestId('preview-iframe')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    // Durante el reintento no debe haber previsualización previa ni error previo
    expect(screen.queryByTestId('preview-iframe')).toBeNull()

    await waitFor(() => {
      expect(screen.getByTestId('preview-iframe')).toBeTruthy()
    })
  })
})


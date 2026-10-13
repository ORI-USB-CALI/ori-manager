import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetchArchivo } from './api'
import { descargarBlob, nombreArchivoDesdeContentDisposition } from './descargas'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('nombreArchivoDesdeContentDisposition (FE-02)', () => {
  it('lee filename entre comillas', () => {
    expect(nombreArchivoDesdeContentDisposition('attachment; filename="Convenio_CONV-1_2026-10-12.pdf"'))
      .toBe('Convenio_CONV-1_2026-10-12.pdf')
  })

  it('lee filename sin comillas', () => {
    expect(nombreArchivoDesdeContentDisposition('attachment; filename=Convenio_1.xlsx'))
      .toBe('Convenio_1.xlsx')
  })

  it('prefiere filename* codificado en UTF-8', () => {
    expect(nombreArchivoDesdeContentDisposition(
      "attachment; filename=\"Convenio.pdf\"; filename*=UTF-8''Convenio_Espa%C3%B1a.pdf",
    )).toBe('Convenio_España.pdf')
  })

  it('devuelve null sin cabecera o sin nombre', () => {
    expect(nombreArchivoDesdeContentDisposition(null)).toBeNull()
    expect(nombreArchivoDesdeContentDisposition('attachment')).toBeNull()
  })
})

describe('descargarBlob (FE-02)', () => {
  it('descarga con un enlace invisible y revoca la URL después', () => {
    vi.useFakeTimers()
    const crear = vi.fn().mockReturnValue('blob:temporal')
    const revocar = vi.fn()
    window.URL.createObjectURL = crear
    window.URL.revokeObjectURL = revocar
    const clics: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clics.push(this)
    })
    const blob = new Blob(['%PDF-'], { type: 'application/pdf' })

    descargarBlob(blob, 'Convenio_1.pdf')

    expect(crear).toHaveBeenCalledWith(blob)
    expect(clics).toHaveLength(1)
    expect(clics[0].download).toBe('Convenio_1.pdf')
    expect(clics[0].getAttribute('href')).toBe('blob:temporal')
    expect(clics[0].style.display).toBe('none')
    // El enlace no queda en el documento.
    expect(document.body.contains(clics[0])).toBe(false)
    // La URL se libera, pero no en el mismo ciclo del clic.
    expect(revocar).not.toHaveBeenCalled()
    vi.runAllTimers()
    expect(revocar).toHaveBeenCalledWith('blob:temporal')
  })
})

describe('apiFetchArchivo (FE-02)', () => {
  it('pide el binario a /api con la sesión y devuelve blob y nombre', async () => {
    const blob = new Blob(['PK'])
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'Content-Disposition': 'attachment; filename="Convenio_1.xlsx"' }),
      blob: () => Promise.resolve(blob),
    })
    vi.stubGlobal('fetch', fetchMock)

    const archivo = await apiFetchArchivo('/convenios/1/exportar?formato=excel')

    expect(fetchMock).toHaveBeenCalledWith('/api/convenios/1/exportar?formato=excel', { credentials: 'include' })
    expect(archivo).toEqual({ blob, nombreArchivo: 'Convenio_1.xlsx' })
  })

  it('expone el 422 de nivel superior (HU-24) como detail del ApiError', async () => {
    const cuerpo = {
      error: 'CONVENIO_INCOMPLETO',
      message: 'No es posible generar el documento oficial. Faltan datos obligatorios.',
      campos_faltantes: ['fecha_fin_vigencia'],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      text: () => Promise.resolve(JSON.stringify(cuerpo)),
    }))

    const error = await apiFetchArchivo('/convenios/1/exportar?formato=pdf').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).message).toBe(cuerpo.message)
    expect((error as ApiError).detail).toEqual(cuerpo)
  })

  it('usa detail cuando la API lo envía', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      text: () => Promise.resolve(JSON.stringify({ detail: 'No tiene permiso para esta operación' })),
    }))

    const error = await apiFetchArchivo('/convenios/1/exportar?formato=pdf').catch((e: unknown) => e)

    expect((error as ApiError).status).toBe(403)
    expect((error as ApiError).message).toBe('No tiene permiso para esta operación')
  })
})

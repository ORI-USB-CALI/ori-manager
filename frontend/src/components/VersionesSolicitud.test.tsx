import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  ComparacionVersiones,
  DocumentoVersion,
  HistorialSolicitud,
  TipoDocumento,
  VersionComparada,
} from '../pages/solicitudes'
import { VersionesSolicitud } from './VersionesSolicitud'

const autor = { id: 5, nombre_completo: 'Solicitante Interna', correo: 'solicitante@example.com' }

function comparada(numero: number): VersionComparada {
  return { numero, radicada_en: `2026-10-0${numero}T15:00:00Z`, radicada_por: autor }
}

function documento(id: number, tipo: TipoDocumento, nombre_archivo: string): DocumentoVersion {
  return { id, tipo, nombre_archivo, tipo_mime: 'application/pdf', tamano_bytes: 100 }
}

const historialDosVersiones: HistorialSolicitud = {
  solicitud_id: 9,
  consecutivo: 'SOL-00000009',
  estado: 'RADICADA',
  versiones: [
    {
      numero: 1,
      radicada_en: '2026-10-01T15:00:00Z',
      devolucion: {
        observaciones: 'Actualizar el RUT',
        devuelta_por_nombre: 'Gestora ORI',
        devuelta_en: '2026-10-01T18:00:00Z',
        corregida_en_version: 2,
      },
    },
    { numero: 2, radicada_en: '2026-10-02T15:00:00Z', devolucion: null },
  ],
}

const comparacion: ComparacionVersiones = {
  solicitud_id: 9,
  version_base: comparada(1),
  version_comparada: comparada(2),
  hay_cambios: true,
  campos: [
    { campo: 'objeto', etiqueta: 'Objeto', valor_anterior: 'Objeto inicial', valor_nuevo: 'Objeto corregido' },
    { campo: 'observaciones', etiqueta: 'Observaciones', valor_anterior: null, valor_nuevo: 'Nueva nota' },
  ],
  documentos: {
    agregados: [documento(3, 'CEDULA_REPRESENTANTE_LEGAL', 'cedula.pdf')],
    sustituidos: [{ tipo: 'RUT', anterior: documento(1, 'RUT', 'rut.pdf'), nuevo: documento(4, 'RUT', 'rut-2026.pdf') }],
    eliminados: [documento(2, 'CAMARA_COMERCIO', 'camara.pdf')],
  },
}

function respuesta(status: number, cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } })
}

function renderizar(rutas: Record<string, Response>) {
  const fetch = vi.fn(async (url: string) => rutas[url]?.clone() ?? respuesta(404, { detail: 'Not Found' }))
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const resultado = render(
    <QueryClientProvider client={cliente}>
      <VersionesSolicitud solicitudId={9} />
    </QueryClientProvider>,
  )
  return { fetch, ...resultado }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('VersionesSolicitud', () => {
  it('lista las radicaciones y compara la más reciente con la anterior', async () => {
    const { fetch } = renderizar({
      '/api/solicitudes/recibidas/9/historial': respuesta(200, historialDosVersiones),
      '/api/solicitudes/recibidas/9/versiones/2/comparacion': respuesta(200, comparacion),
    })

    const radicaciones = await screen.findByRole('list', { name: 'Radicaciones de la solicitud' })
    expect(within(radicaciones).getAllByRole('listitem')).toHaveLength(2)
    expect(within(radicaciones).getByText('Actualizar el RUT')).toBeTruthy()
    expect(within(radicaciones).getByText(/Gestora ORI/)).toBeTruthy()
    expect(within(radicaciones).getByText('Corregida en la versión 2')).toBeTruthy()

    const tabla = await screen.findByRole('table', { name: 'Campos modificados' })
    const objeto = within(tabla).getByRole('row', { name: /Objeto inicial/ })
    expect(within(objeto).getByText('Objeto corregido')).toBeTruthy()
    const observaciones = within(tabla).getByRole('row', { name: /Nueva nota/ })
    expect(within(observaciones).getByText('—')).toBeTruthy()

    const documentos = screen.getByRole('list', { name: 'Cambios en documentos' })
    const filas = within(documentos).getAllByRole('listitem')
    expect(filas).toHaveLength(3)
    expect(within(filas[0]).getByText('Agregado')).toBeTruthy()
    expect(filas[0].textContent).toContain('cedula.pdf (Cédula del representante legal)')
    expect(within(filas[1]).getByText('Sustituido')).toBeTruthy()
    expect(filas[1].textContent).toContain('rut.pdf (RUT) → rut-2026.pdf (RUT)')
    expect(within(filas[2]).getByText('Eliminado')).toBeTruthy()
    expect(filas[2].textContent).toContain('camara.pdf (Cámara de Comercio)')

    const selector = screen.getByLabelText('Comparar con la versión anterior') as HTMLSelectElement
    expect(selector.value).toBe('2')
    expect(within(selector).getAllByRole('option')).toHaveLength(1)
    expect(fetch).toHaveBeenCalledWith('/api/solicitudes/recibidas/9/versiones/2/comparacion', expect.anything())
  })

  it('con una sola versión indica que no hay cambios que comparar', async () => {
    const { fetch } = renderizar({
      '/api/solicitudes/recibidas/9/historial': respuesta(200, {
        ...historialDosVersiones,
        versiones: [{ numero: 1, radicada_en: '2026-10-01T15:00:00Z', devolucion: null }],
      }),
    })

    expect(await screen.findByText('Solo existe la radicación inicial; no hay cambios que comparar.')).toBeTruthy()
    expect(screen.queryByLabelText('Comparar con la versión anterior')).toBeNull()
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('se oculta cuando el servidor responde 403', async () => {
    const { fetch, container } = renderizar({
      '/api/solicitudes/recibidas/9/historial': respuesta(403, { detail: 'No tiene permiso para esta operación' }),
    })

    await waitFor(() => expect(fetch).toHaveBeenCalled())
    await waitFor(() => expect(container.innerHTML).toBe(''))
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

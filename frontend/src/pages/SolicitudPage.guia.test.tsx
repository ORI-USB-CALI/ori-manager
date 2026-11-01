import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationProvider } from '../app/notifications/Notifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { TourProvider } from '../components/TourProvider'
import type { CatalogosSolicitud } from './solicitudes'
import { DESTINOS_SECCIONES_SOLICITUD } from './guiaRadicacion'
import type { EstadoGuia } from './guias'
import { SolicitudPage } from './SolicitudPage'

const CATALOGOS: CatalogosSolicitud = {
  solicitante: {
    tipo_usuario: 'INTERNO', tipo_unidad: 'FACULTAD', nombre: 'Ana', correo: 'ana@usb.edu.co',
    identificacion: null, entidad: null, cargo: 'Docente', unidad: 'Ingeniería', programa: null,
  },
  tipos_convenio: [{ id: 1, codigo: 'MARCO', nombre: 'Marco', naturaleza: 'MARCO' }],
  tipos_documento: [{ codigo: 'CAMARA_COMERCIO', nombre: 'Cámara de Comercio', es_representacion_legal: true }],
  requiere_documento_representacion: true,
}

const tituloActual = () => document.querySelector('.driver-popover-title')?.textContent

function preparar(estado: EstadoGuia = 'PENDIENTE', { fallaGuardado = false } = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const sesion: Sesion = {
    id: 1, correo: 'ana@usb.edu.co', nombre_completo: 'Ana', activo: true, tipo_usuario: 'INTERNO',
    rol: { codigo: 'SOLICITANTE_INTERNO', nombre: 'Solicitante interno' },
    permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/solicitudes/catalogos')) return Response.json(CATALOGOS)
    if (url.endsWith('/guias/GUIA_RADICACION') && init?.method === 'PUT') {
      if (fallaGuardado) return Response.json({ detail: 'Servicio no disponible' }, { status: 503 })
      const cuerpo = JSON.parse(String(init.body)) as { estado: EstadoGuia }
      return Response.json({ guia: 'GUIA_RADICACION', estado: cuerpo.estado, version: 1, actualizado_en: null })
    }
    if (url.endsWith('/guias/GUIA_RADICACION')) {
      return Response.json({ guia: 'GUIA_RADICACION', estado, version: null, actualizado_en: null })
    }
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationProvider>
        <TourProvider>
          <MemoryRouter initialEntries={['/solicitudes/nueva']}>
            <Routes><Route path="/solicitudes/nueva" element={<SolicitudPage />} /></Routes>
          </MemoryRouter>
        </TourProvider>
      </NotificationProvider>
    </QueryClientProvider>,
  )
  const guardados = () => fetch.mock.calls
    .filter(([, init]) => init?.method === 'PUT')
    .map(([, init]) => JSON.parse(String(init?.body)) as { estado: EstadoGuia })
  return { fetch, guardados, cliente }
}

async function abrirGuia(cliente: QueryClient) {
  await waitFor(() => expect(document.querySelector('[data-tour="solicitud-observaciones"]')).not.toBeNull())
  fireEvent.click(screen.getByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' }))
  await waitFor(() => expect(tituloActual()).toBe('1. Información del solicitante'))
  // El estado de la guía se consulta al abrirla.
  await waitFor(() => expect(cliente.getQueryData(['guias', 'GUIA_RADICACION'])).toBeDefined())
}

beforeEach(() => {
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
    return { length: this.hasAttribute('data-tour') ? 1 : 0 } as DOMRectList
  })
})

afterEach(() => {
  cleanup()
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('guía de radicación en el formulario (HU-39 FE01)', () => {
  it('marca las ocho secciones del formulario para la guía', async () => {
    preparar()
    for (const destino of Object.values(DESTINOS_SECCIONES_SOLICITUD)) {
      await waitFor(() => expect(document.querySelector(`[data-tour="${destino}"]`)).not.toBeNull())
    }
  })

  it('no abre la guía sola ni consulta su estado al cargar (RN-07)', async () => {
    const { fetch } = preparar()
    await screen.findByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' })
    expect(document.querySelector('.driver-popover')).toBeNull()
    expect(fetch.mock.calls.some(([url]) => String(url).includes('/guias'))).toBe(false)
  })

  it('al finalizar registra COMPLETADO sin guardar ni radicar la solicitud (CA-07)', async () => {
    const { fetch, guardados, cliente } = preparar()
    await abrirGuia(cliente)

    // Avanzar por las ocho secciones originales
for (let paso = 1; paso < 8; paso++) {
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
}

await waitFor(() =>
  expect(tituloActual()).toBe('8. Observaciones adicionales'),
)

// Comprobar que el recorrido continúa con FE-03
fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))

await waitFor(() =>
  expect(tituloActual()).not.toBe('8. Observaciones adicionales'),
)

// Avanzar por los pasos adicionales hasta encontrar Finalizar
for (let paso = 0; paso < 20; paso++) {
  if (screen.queryByRole('button', { name: 'Finalizar' })) break

  fireEvent.click(
    screen.getByRole('button', { name: 'Siguiente' }),
  )
}

// Finalizar el recorrido completo
fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }))

    await waitFor(() => expect(guardados()).toEqual([{ estado: 'COMPLETADO', version: 1 }]))
    const rutas = fetch.mock.calls.map(([url, init]) => `${init?.method ?? 'GET'} ${url}`)
    expect(rutas.filter((ruta) => ruta.includes('/solicitudes') && !ruta.includes('/catalogos'))).toEqual([])
  })

  it('omitir una guía pendiente registra OMITIDO', async () => {
    const { guardados, cliente } = preparar('PENDIENTE')
    await abrirGuia(cliente)

    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))

    await waitFor(() => expect(guardados()).toEqual([{ estado: 'OMITIDO', version: 1 }]))
  })

  it('cerrar una guía ya completada no cambia su estado (RN-05)', async () => {
    const { guardados, cliente } = preparar('COMPLETADO')
    await abrirGuia(cliente)

    fireEvent.click(screen.getByRole('button', { name: 'Omitir recorrido' }))

    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())
    expect(guardados()).toEqual([])
  })

  it('si falla el guardado lo informa y el formulario sigue disponible', async () => {
    const { cliente } = preparar('PENDIENTE', { fallaGuardado: true })
    await abrirGuia(cliente)

    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))

    expect(await screen.findByText(/No se pudo guardar el estado de la guía/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Guardar borrador' })).toBeTruthy()
  })
})

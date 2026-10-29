import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NotificationProvider } from '../app/notifications/Notifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { TourProvider } from '../components/TourProvider'
import { DESTINOS_SECCIONES_SOLICITUD } from './guiaRadicacion'
import { SolicitudPage } from './SolicitudPage'
import type { CatalogosSolicitud } from './solicitudes'

/**
 * HT14-FE02: la guía de radicación (HU-39) se integra en el mismo formulario
 * que las validaciones de formato (HT-14). Estas pruebas cubren justo esa
 * intersección, no las reglas de formato en sí (eso ya lo cubre HT14-FE01)
 * ni el comportamiento general de la guía (eso ya lo cubre HU-39 FE01/FE03
 * en SolicitudPage.guia.test.tsx): que una no rompa a la otra.
 */
const CATALOGOS_EXTERNO: CatalogosSolicitud = {
  solicitante: {
    tipo_usuario: 'EXTERNO', tipo_unidad: null, nombre: 'Carlos Pérez', correo: 'carlos@externo.com',
    identificacion: null, entidad: null, cargo: null, unidad: null, programa: null,
  },
  tipos_convenio: [{ id: 1, codigo: 'MARCO', nombre: 'Marco', naturaleza: 'MARCO' }],
  tipos_documento: [{ codigo: 'CAMARA_COMERCIO', nombre: 'Cámara de Comercio', es_representacion_legal: true }],
  requiere_documento_representacion: true,
}

function prepararExterno() {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const sesion: Sesion = {
    id: 9, correo: 'carlos@externo.com', nombre_completo: 'Carlos Pérez', activo: true, tipo_usuario: 'EXTERNO',
    rol: { codigo: 'SOLICITANTE_EXTERNO', nombre: 'Solicitante externo' },
    permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  const fetch = vi.fn(async (url: string) => {
    if (url.endsWith('/solicitudes/catalogos')) return Response.json(CATALOGOS_EXTERNO)
    if (url.endsWith('/paises')) return Response.json([{ id: 1, codigo_iso: 'CO', nombre: 'Colombia' }])
    if (url.endsWith('/guias/GUIA_RADICACION')) {
      return Response.json({ guia: 'GUIA_RADICACION', estado: 'PENDIENTE', version: null, actualizado_en: null })
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
}

function seccion(destino: string) {
  const elemento = document.querySelector(`[data-tour="${destino}"]`)
  if (!elemento) throw new Error(`No se encontró la sección ${destino}`)
  return within(elemento as HTMLElement)
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

describe('regresión HT-14 + HU-39: las validaciones y la guía conviven (HT14-FE02)', () => {
  it('marca la sección 1 también para el solicitante externo, con el tipo de documento y el dígito de verificación de HT-14', async () => {
    prepararExterno()
    await waitFor(() => expect(document.querySelector(`[data-tour="${DESTINOS_SECCIONES_SOLICITUD.solicitante}"]`)).not.toBeNull())
    const uno = seccion(DESTINOS_SECCIONES_SOLICITUD.solicitante)
    expect(uno.getByLabelText('Tipo de documento *')).toBeTruthy()
    expect(uno.queryByLabelText('Dígito de verificación *')).toBeNull()

    await userEvent.setup().selectOptions(uno.getByLabelText('Tipo de documento *'), 'NIT')
    expect(seccion(DESTINOS_SECCIONES_SOLICITUD.solicitante).getByLabelText('Dígito de verificación *')).toBeTruthy()
  })

  it('el dígito de verificación de la contraparte sigue validándose dentro del formulario integrado con la guía', async () => {
    const user = userEvent.setup()
    prepararExterno()
    const dos = () => seccion(DESTINOS_SECCIONES_SOLICITUD.contraparte)
    await waitFor(() => expect(document.querySelector(`[data-tour="${DESTINOS_SECCIONES_SOLICITUD.contraparte}"]`)).not.toBeNull())

    await user.selectOptions(dos().getByLabelText('Tipo de identificación *'), 'NIT')
    await user.type(dos().getByLabelText('Identificación *'), '900123456')
    const dv = dos().getByLabelText('Dígito de verificación *')
    await user.type(dv, '0')
    await user.tab()
    expect(await screen.findByText('El dígito de verificación del NIT no es correcto')).toBeTruthy()

    await user.clear(dv)
    await user.type(dv, '8')
    await user.tab()
    await waitFor(() => expect(screen.queryByText('El dígito de verificación del NIT no es correcto')).toBeNull())
  })

  it('abrir y cerrar la guía no modifica un valor ni un error de validación ya diligenciados', async () => {
    const user = userEvent.setup()
    prepararExterno()
    const telefono = await screen.findByRole('textbox', { name: 'Teléfono institucional *' })
    await user.type(telefono, 'abc')
    await user.tab()
    expect(await screen.findByText(/Ingrese un teléfono válido/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' }))
    await waitFor(() => expect(document.querySelector('.driver-popover')).not.toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(document.querySelector('.driver-popover')).toBeNull())

    expect(screen.getByText(/Ingrese un teléfono válido/)).toBeTruthy()
    expect((telefono as HTMLInputElement).value).toBe('abc')
  })
})

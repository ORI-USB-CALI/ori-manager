import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppLayout } from '../app/AppLayout'
import { NotificationProvider } from '../app/notifications/Notifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { TourProvider } from '../components/TourProvider'
import { SolicitudPage } from './SolicitudPage'
import type { CatalogosSolicitud } from './solicitudes'

/**
 * HU-39 FE04: pruebas funcionales y de accesibilidad de la guía de radicación
 * ya integrada (FE01 + FE02 + FE03) y su convivencia con el onboarding de
 * HU-38 (FE-03). Complementa SolicitudPage.guia.test.tsx (apertura manual,
 * estados COMPLETADO/OMITIDO, sin efectos sobre la solicitud) y
 * TourProvider.test.tsx (motor con pasos sintéticos).
 */
type Rol = 'SOLICITANTE_INTERNO' | 'SOLICITANTE_EXTERNO'

const TITULOS_RECORRIDO = [
  '1. Información del solicitante',
  '2. Información de la contraparte',
  '3. Contacto de contraparte',
  '4. Información del convenio',
  '5. Supervisor o encargado de ejecución USB',
  '6. Supervisor o encargado de ejecución de la contraparte',
  '7. Documentación',
  '8. Observaciones adicionales',
  'Adjuntar documentos',
  'Guardar borrador',
  'Radicar la solicitud',
  'Cómo corregir errores de validación',
  'Consultar Mis solicitudes',
]

class SocketPrueba {
  close = vi.fn()
  constructor(public url: string) {}
}

function sesionDe(rol: Rol): Sesion {
  return {
    id: 5, correo: 'persona@example.com', nombre_completo: 'Persona', activo: true,
    tipo_usuario: rol === 'SOLICITANTE_INTERNO' ? 'INTERNO' : 'EXTERNO',
    rol: { codigo: rol, nombre: rol },
    permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
  }
}

function catalogosDe(rol: Rol): CatalogosSolicitud {
  const interno = rol === 'SOLICITANTE_INTERNO'
  return {
    solicitante: {
      tipo_usuario: interno ? 'INTERNO' : 'EXTERNO', tipo_unidad: interno ? 'FACULTAD' : null,
      nombre: 'Persona', correo: 'persona@example.com', identificacion: null,
      entidad: interno ? null : 'Empresa Aliada', cargo: interno ? 'Docente' : null,
      unidad: interno ? 'Ingeniería' : null, programa: null,
    },
    tipos_convenio: [{ id: 1, codigo: 'MARCO', nombre: 'Marco', naturaleza: 'MARCO' }],
    tipos_documento: [{ codigo: 'CAMARA_COMERCIO', nombre: 'Cámara de Comercio', es_representacion_legal: true }],
    requiere_documento_representacion: true,
  }
}

/** Monta el formulario dentro del AppLayout real, donde también vive el onboarding de HU-38. */
function montar(rol: Rol = 'SOLICITANTE_INTERNO') {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesionDe(rol))
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/solicitudes/catalogos')) return Response.json(catalogosDe(rol))
    if (url.endsWith('/notificaciones')) return Response.json([])
    if (url.endsWith('/notificaciones/ws-ticket')) return Response.json({ ticket: 'ticket' })
    const guia = /\/guias\/(ONBOARDING_INICIAL|GUIA_RADICACION)$/.exec(url)?.[1]
    if (guia && init?.method === 'PUT') {
      const cuerpo = JSON.parse(String(init.body)) as { estado: string }
      return Response.json({ guia, estado: cuerpo.estado, version: 1, actualizado_en: null })
    }
    // El onboarding ya se completó: no se abre solo y no interfiere con la guía.
    if (guia) return Response.json({ guia, estado: guia === 'ONBOARDING_INICIAL' ? 'COMPLETADO' : 'PENDIENTE', version: 1, actualizado_en: null })
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  vi.stubGlobal('WebSocket', SocketPrueba)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationProvider>
        <TourProvider>
          <RouterProvider router={createMemoryRouter([{
            element: <AppLayout />,
            children: [{ path: '/solicitudes/nueva', element: <SolicitudPage /> }],
          }], { initialEntries: ['/solicitudes/nueva'] })} />
        </TourProvider>
      </NotificationProvider>
    </QueryClientProvider>,
  )
  const guardados = (guia: string) => fetch.mock.calls
    .filter(([url, init]) => init?.method === 'PUT' && String(url).endsWith(`/guias/${guia}`))
    .map(([, init]) => (JSON.parse(String(init?.body)) as { estado: string }).estado)
  const onboardingCargado = () => waitFor(() => expect(cliente.getQueryData(['guias', 5, 'ONBOARDING_INICIAL'])).toBeDefined())
  return { guardados, onboardingCargado }
}

// driver.js ignora las flechas mientras anima el cambio de paso (400 ms por defecto),
// y el título del paso aparece a mitad de esa animación.
const esperarTransicion = () => new Promise((resolver) => setTimeout(resolver, 450))

const popover = () => document.querySelector('.driver-popover')
const tituloActual = () => document.querySelector('.driver-popover-title')?.textContent
const descripcionActual = () => document.querySelector('.driver-popover-description')?.textContent ?? ''
const botonGuia = () => screen.getByRole('button', { name: 'Ayuda: cómo diligenciar la solicitud' })
const botonOnboarding = () => screen.getByRole('button', { name: 'Ayuda' })

async function abrirGuia() {
  await waitFor(() => expect(document.querySelector('[data-tour="solicitud-observaciones"]')).not.toBeNull())
  fireEvent.click(botonGuia())
  await waitFor(() => expect(tituloActual()).toBe(TITULOS_RECORRIDO[0]))
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

describe('HU-39 FE04: recorrido completo por tipo de solicitante', () => {
  it.each<Rol>(['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'])(
    'recorre las ocho secciones y las acciones en orden y registra COMPLETADO para %s (CA-02, CA-04, CA-08)',
    async (rol) => {
      const { guardados } = montar(rol)
      await abrirGuia()

      const vistos = [tituloActual()]
      while (!screen.queryByRole('button', { name: 'Finalizar' })) {
        fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
        await waitFor(() => expect(tituloActual()).not.toBe(vistos.at(-1)))
        vistos.push(tituloActual())
      }
      expect(vistos).toEqual(TITULOS_RECORRIDO)
      expect(screen.getByText(`${TITULOS_RECORRIDO.length} de ${TITULOS_RECORRIDO.length}`)).toBeTruthy()

      fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }))
      await waitFor(() => expect(guardados('GUIA_RADICACION')).toEqual(['COMPLETADO']))
      expect(popover()).toBeNull()
      // CA-08: termina sin abandonar el formulario y se puede volver a reproducir.
      expect(screen.getByRole('heading', { name: 'Nueva solicitud' })).toBeTruthy()
      expect((botonGuia() as HTMLButtonElement).disabled).toBe(false)
    },
    // Trece pasos con su animación: con la suite en paralelo supera los 5 s por defecto.
    20_000,
  )

  it('adapta la sección del solicitante al rol (CA-03)', async () => {
    montar('SOLICITANTE_EXTERNO')
    await abrirGuia()
    expect(descripcionActual()).toMatch(/tipo de documento/)
    expect(descripcionActual()).not.toMatch(/Facultad o Dependencia/)
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(popover()).toBeNull())
    cleanup()

    montar('SOLICITANTE_INTERNO')
    await abrirGuia()
    expect(descripcionActual()).toMatch(/Facultad o Dependencia/)
    expect(descripcionActual()).not.toMatch(/tipo de documento/)
  })
})

describe('HU-39 FE04: teclado y accesibilidad', () => {
  it('avanza y retrocede con las flechas del teclado', async () => {
    const user = userEvent.setup()
    montar()
    await abrirGuia()
    await esperarTransicion()

    await user.keyboard('{ArrowRight}')
    await waitFor(() => expect(tituloActual()).toBe(TITULOS_RECORRIDO[1]))
    await esperarTransicion()
    await user.keyboard('{ArrowLeft}')
    await waitFor(() => expect(tituloActual()).toBe(TITULOS_RECORRIDO[0]))
  })

  it('Esc cierra la guía como una omisión y registra OMITIDO (RN-04)', async () => {
    const user = userEvent.setup()
    const { guardados } = montar()
    await abrirGuia()

    await user.keyboard('{Escape}')

    await waitFor(() => expect(popover()).toBeNull())
    await waitFor(() => expect(guardados('GUIA_RADICACION')).toEqual(['OMITIDO']))
    expect((botonGuia() as HTMLButtonElement).disabled).toBe(false)
  })

  it('los controles del globo tienen nombre accesible y el paso indica su progreso', async () => {
    montar()
    await abrirGuia()
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Omitir' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Omitir recorrido' })).toBeTruthy()
    expect(screen.getByText(`1 de ${TITULOS_RECORRIDO.length}`)).toBeTruthy()
  })
})

describe('HU-39 FE04: compatibilidad con el onboarding de HU-38 (RN-06)', () => {
  it('con la guía de radicación abierta no se puede abrir el onboarding', async () => {
    const { guardados } = montar()
    await abrirGuia()

    expect((botonOnboarding() as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(botonOnboarding())
    expect(tituloActual()).toBe(TITULOS_RECORRIDO[0])
    expect(document.querySelectorAll('.driver-popover')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(popover()).toBeNull())
    await waitFor(() => expect((botonOnboarding() as HTMLButtonElement).disabled).toBe(false))
    expect(guardados('ONBOARDING_INICIAL')).toEqual([])
  })

  it('con el onboarding abierto no se puede abrir la guía de radicación', async () => {
    const { guardados, onboardingCargado } = montar()
    await onboardingCargado()
    fireEvent.click(botonOnboarding())
    await waitFor(() => expect(tituloActual()).toBe('¡Bienvenido a ORI Manager!'))

    expect((botonGuia() as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(botonGuia())
    expect(tituloActual()).toBe('¡Bienvenido a ORI Manager!')
    expect(document.querySelectorAll('.driver-popover')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(popover()).toBeNull())
    // Cerrar el onboarding ya completado no cambia su estado ni el de la otra guía (HU-38 CA-07, RN-02).
    expect(guardados('ONBOARDING_INICIAL')).toEqual([])
    expect(guardados('GUIA_RADICACION')).toEqual([])
    await waitFor(() => expect((botonGuia() as HTMLButtonElement).disabled).toBe(false))
  })

  it('el estado de cada guía se guarda por separado (RN-02)', async () => {
    const { guardados } = montar()
    await abrirGuia()
    fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))
    await waitFor(() => expect(guardados('GUIA_RADICACION')).toEqual(['OMITIDO']))
    expect(guardados('ONBOARDING_INICIAL')).toEqual([])
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pasosVisibles, type PasoRecorrido } from '../components/recorrido'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { HomePage } from '../pages/HomePage'
import { AppLayout } from './AppLayout'

/**
 * HU-38 FE-04: los identificadores (`data-tour`) que el contenido del
 * onboarding (HU-38 FE-02, ver pasosOnboardingInicial) espera encontrar sobre
 * el header responsive (HT-04) y la página de Inicio. No arma el recorrido
 * completo (eso lo prueba HU-39 FE04 más adelante con el onboarding ya
 * integrado): solo comprueba que cada destino existe en el DOM real y que el
 * motor (pasosVisibles) lo considera visible.
 */
class SocketPrueba {
  close = vi.fn()
  constructor(public url: string) {}
}

const DESTINOS_INICIO = [
  'inicio-accesos-rapidos',
  'inicio-nueva-solicitud',
  'inicio-mis-solicitudes',
  'navegacion-principal',
  'centro-notificaciones',
] as const

function sesionSolicitante(codigo: 'SOLICITANTE_INTERNO' | 'SOLICITANTE_EXTERNO' = 'SOLICITANTE_INTERNO'): Sesion {
  return {
    id: 7, correo: 'ana@usb.edu.co', nombre_completo: 'Ana', activo: true,
    tipo_usuario: codigo === 'SOLICITANTE_INTERNO' ? 'INTERNO' : 'EXTERNO',
    rol: { codigo, nombre: codigo },
    permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
  }
}

function montar(sesion: Sesion) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, sesion)
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/notificaciones')) return Response.json([])
    if (url.endsWith('/notificaciones/ws-ticket')) return Response.json({ ticket: 'ticket-prueba' })
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  }))
  vi.stubGlobal('WebSocket', SocketPrueba)
  render(
    <QueryClientProvider client={cliente}>
      <RouterProvider router={createMemoryRouter([{
        element: <AppLayout />,
        children: [{ path: '/', element: <HomePage /> }],
      }])} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  // jsdom no calcula diseño: un destino con data-tour se trata como visible,
  // igual que en las pruebas de HU-38/HU-39 (SolicitudPage.guia.test.tsx).
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
    return { length: this.hasAttribute('data-tour') ? 1 : 0 } as DOMRectList
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('HU-38 FE-04: identificadores estables del recorrido', () => {
  it.each(['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'] as const)(
    'marca en Inicio y en la navegación los cinco destinos que espera el onboarding para %s',
    async (rol) => {
      montar(sesionSolicitante(rol))
      await screen.findByRole('heading', { name: 'Accesos rápidos' })
      for (const destino of DESTINOS_INICIO) {
        await waitFor(() => expect(document.querySelector(`[data-tour="${destino}"]`)).not.toBeNull())
      }
    },
  )

  it('el motor considera visibles los cinco destinos (pasosVisibles no descarta ninguno)', async () => {
    montar(sesionSolicitante())
    await screen.findByRole('heading', { name: 'Accesos rápidos' })
    const pasos: PasoRecorrido[] = DESTINOS_INICIO.map((destino) => ({
      destino, titulo: destino, descripcion: 'Paso de prueba',
    }))
    const visibles = pasosVisibles(pasos, { rol: { codigo: 'SOLICITANTE_INTERNO', nombre: '' }, permisos: [] })
    expect(visibles).toHaveLength(DESTINOS_INICIO.length)
  })

  it('no marca los accesos de Nueva solicitud ni Mis solicitudes para quien no tiene esos permisos', async () => {
    const sesion: Sesion = {
      id: 1, correo: 'gestor@usb.edu.co', nombre_completo: 'Gestor', activo: true, tipo_usuario: 'INTERNO',
      rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos: ['convenios.ver'],
    }
    montar(sesion)
    await screen.findByRole('heading', { name: 'Accesos rápidos' })
    expect(document.querySelector('[data-tour="inicio-nueva-solicitud"]')).toBeNull()
    expect(document.querySelector('[data-tour="inicio-mis-solicitudes"]')).toBeNull()
    // Los destinos del header y de notificaciones no dependen del rol.
    expect(document.querySelector('[data-tour="navegacion-principal"]')).not.toBeNull()
    expect(document.querySelector('[data-tour="centro-notificaciones"]')).not.toBeNull()
  })
})

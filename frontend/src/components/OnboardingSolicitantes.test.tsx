import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Sesion } from '../auth/sesion'
import { OnboardingSolicitantes } from './OnboardingSolicitantes'
import type { OpcionesRecorrido } from './recorrido'

const iniciar = vi.hoisted(() => vi.fn((_opciones: OpcionesRecorrido) => true))
vi.mock('./recorrido', () => ({
  useRecorrido: () => ({ activo: null, iniciar }),
}))

const solicitante: Sesion = {
  id: 9, correo: 'solicitante@example.test', nombre_completo: 'Persona de prueba',
  activo: true, tipo_usuario: 'EXTERNO', rol: { codigo: 'SOLICITANTE_EXTERNO', nombre: 'Solicitante externo' },
  permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
}

function montar(estado: 'PENDIENTE' | 'COMPLETADO' | 'OMITIDO', ruta = '/', sesion = solicitante) {
  const consulta = { guia: 'ONBOARDING_INICIAL', estado, version: 1, actualizado_en: null }
  const fetchSimulado = vi.fn().mockImplementation(async (_url: string, options?: RequestInit) => ({
    ok: true, status: 200,
    json: async () => options?.method === 'PUT'
      ? { ...consulta, ...JSON.parse(options.body as string) }
      : consulta,
  }))
  vi.stubGlobal('fetch', fetchSimulado)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[ruta]}>
        <OnboardingSolicitantes sesion={sesion} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return fetchSimulado
}

beforeEach(() => iniciar.mockClear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HU-38 FE-03: activación y persistencia', () => {
  it('abre automáticamente solo si está PENDIENTE en Inicio', async () => {
    montar('PENDIENTE')
    await waitFor(() => expect(iniciar).toHaveBeenCalledTimes(1))
    expect(iniciar.mock.calls[0][0].guia).toBe('ONBOARDING_INICIAL')
  })

  it('no abre automáticamente una guía COMPLETADA', async () => {
    const fetchSimulado = montar('COMPLETADO')
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalled())
    expect(iniciar).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Ayuda' }))
    expect(iniciar).toHaveBeenCalledTimes(1)
  })

  it('no inicia automáticamente fuera de Inicio, pero permite abrir Ayuda', async () => {
    const fetchSimulado = montar('PENDIENTE', '/solicitudes')
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalled())
    expect(iniciar).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Ayuda' }))
    expect(iniciar).toHaveBeenCalledTimes(1)
  })

  it('registra COMPLETADO tras finalizar y OMITIDO al cerrar un pendiente', async () => {
    const fetchSimulado = montar('PENDIENTE')
    await waitFor(() => expect(iniciar).toHaveBeenCalledTimes(1))
    const opciones = iniciar.mock.calls[0][0]
    opciones.onComplete?.()
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(2))
    expect(JSON.parse(fetchSimulado.mock.calls[1][1].body).estado).toBe('COMPLETADO')
  })

  it('no envía OMITIDO cuando se reproduce un onboarding ya completado', async () => {
    const fetchSimulado = montar('COMPLETADO')
    await waitFor(() => expect(fetchSimulado).toHaveBeenCalledTimes(1))
    await userEvent.click(screen.getByRole('button', { name: 'Ayuda' }))
    iniciar.mock.calls[0][0].onSkip?.()
    expect(fetchSimulado).toHaveBeenCalledTimes(1)
  })

  it('no muestra el botón ni consulta la API para roles distintos de solicitante', () => {
    const admin: Sesion = { ...solicitante, rol: { codigo: 'ADMINISTRADOR_ORI', nombre: 'Admin' } }
    const fetchSimulado = montar('PENDIENTE', '/', admin)
    expect(screen.queryByRole('button', { name: 'Ayuda' })).toBeNull()
    expect(fetchSimulado).not.toHaveBeenCalled()
  })
})

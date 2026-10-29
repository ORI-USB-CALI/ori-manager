import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type CodigoRol, type Permiso, type Sesion } from '../auth/sesion'
import { type ContextoRecorrido, type PasoRecorrido, useRecorrido } from './recorrido'
import { TourProvider } from './TourProvider'

const PASOS: PasoRecorrido[] = [
  { titulo: 'Bienvenida', descripcion: 'Qué es ORI Manager' },
  { titulo: 'Proceso', descripcion: 'Etapas de una solicitud' },
  { titulo: 'Seguimiento', descripcion: 'Mis solicitudes' },
]

let contexto: ContextoRecorrido

function Capturar() {
  const valor = useRecorrido()
  useEffect(() => { contexto = valor })
  return <p>Guía activa: {valor.activo ?? 'ninguna'}</p>
}

function preparar({ rol = 'SOLICITANTE_INTERNO', permisos = ['solicitudes.crear'] }: {
  rol?: CodigoRol; permisos?: Permiso[]
} = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const sesion: Sesion = {
    id: 1, correo: 'solicitante@example.com', nombre_completo: 'Solicitante', activo: true,
    tipo_usuario: 'INTERNO', rol: { codigo: rol, nombre: rol }, permisos,
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  return render(
    <QueryClientProvider client={cliente}>
      <TourProvider><Capturar /></TourProvider>
    </QueryClientProvider>,
  )
}

function iniciar(pasos = PASOS) {
  const onComplete = vi.fn()
  const onSkip = vi.fn()
  let abierto = false
  act(() => { abierto = contexto.iniciar({ guia: 'ONBOARDING_INICIAL', pasos, onComplete, onSkip }) })
  return { abierto, onComplete, onSkip }
}

const tituloActual = () => document.querySelector('.driver-popover-title')?.textContent

beforeEach(() => {
  // jsdom no calcula diseño: se simula que todo elemento con data-tour está visible.
  vi.spyOn(Element.prototype, 'getClientRects').mockImplementation(function (this: Element) {
    const visible = this.hasAttribute('data-tour') && !this.closest('[hidden]')
    return { length: visible ? 1 : 0 } as DOMRectList
  })
})

afterEach(() => {
  cleanup()
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})

describe('motor de recorridos', () => {
  it('avanza, retrocede y al finalizar informa onComplete', async () => {
    preparar()
    const { abierto, onComplete, onSkip } = iniciar()
    expect(abierto).toBe(true)
    expect(screen.getByText('Guía activa: ONBOARDING_INICIAL')).toBeTruthy()

    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))
    expect(screen.getByText('1 de 3')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(tituloActual()).toBe('Proceso'))
    fireEvent.click(screen.getByRole('button', { name: 'Anterior' }))
    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(tituloActual()).toBe('Seguimiento'))
    fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }))

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce())
    expect(onSkip).not.toHaveBeenCalled()
    expect(screen.getByText('Guía activa: ninguna')).toBeTruthy()
    expect(document.querySelector('.driver-popover')).toBeNull()
  })

  it.each([
    ['Omitir', () => fireEvent.click(screen.getByRole('button', { name: 'Omitir' }))],
    ['la X', () => fireEvent.click(screen.getByRole('button', { name: 'Omitir recorrido' }))],
    ['Esc', () => userEvent.keyboard('{Escape}')],
  ])('%s informa onSkip y no onComplete', async (_, cerrar) => {
    preparar()
    const { onComplete, onSkip } = iniciar()
    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))

    await act(async () => { await cerrar() })

    await waitFor(() => expect(onSkip).toHaveBeenCalledOnce())
    expect(onComplete).not.toHaveBeenCalled()
    expect(screen.getByText('Guía activa: ninguna')).toBeTruthy()
    expect(document.querySelector('.driver-popover')).toBeNull()
  })

  it('muestra un solo botón Omitir aunque se cambie de paso', async () => {
    preparar()
    iniciar()
    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))
    fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await waitFor(() => expect(tituloActual()).toBe('Proceso'))

    expect(screen.getAllByRole('button', { name: 'Omitir' })).toHaveLength(1)
  })

  it('no abre un segundo recorrido mientras otro está abierto', async () => {
    preparar()
    iniciar()
    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))

    let segundo = true
    act(() => { segundo = contexto.iniciar({ guia: 'GUIA_RADICACION', pasos: PASOS }) })

    expect(segundo).toBe(false)
    expect(screen.getByText('Guía activa: ONBOARDING_INICIAL')).toBeTruthy()
  })

  it('filtra los pasos por permiso y por rol', async () => {
    preparar({ rol: 'SOLICITANTE_EXTERNO', permisos: ['solicitudes.crear'] })
    iniciar([
      { titulo: 'Para todos', descripcion: '.' },
      { titulo: 'Con permiso', descripcion: '.', permiso: 'solicitudes.crear' },
      { titulo: 'Sin permiso', descripcion: '.', permiso: 'convenios.revisar_contraparte_propia' },
      { titulo: 'Solo internos', descripcion: '.', roles: ['SOLICITANTE_INTERNO'] },
      { titulo: 'Solo externos', descripcion: '.', roles: ['SOLICITANTE_EXTERNO'] },
    ])

    await waitFor(() => expect(screen.getByText('1 de 3')).toBeTruthy())
    const titulos = [tituloActual()]
    for (let i = 0; i < 2; i++) {
      fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
      await waitFor(() => expect(tituloActual()).not.toBe(titulos.at(-1)))
      titulos.push(tituloActual())
    }
    expect(titulos).toEqual(['Para todos', 'Con permiso', 'Solo externos'])
  })

  it('omite los pasos cuyo destino no existe o está oculto y resalta los visibles', async () => {
    preparar()
    document.body.insertAdjacentHTML('beforeend', `
      <a data-tour="inicio">Inicio</a>
      <nav hidden><a data-tour="menu-movil">Mis solicitudes</a></nav>`)
    iniciar([
      { titulo: 'Inicio', descripcion: '.', destino: 'inicio' },
      { titulo: 'Oculto', descripcion: '.', destino: 'menu-movil' },
      { titulo: 'Ausente', descripcion: '.', destino: 'no-existe' },
    ])

    await waitFor(() => expect(tituloActual()).toBe('Inicio'))
    expect(screen.getByText('1 de 1')).toBeTruthy()
    expect(document.querySelector('[data-tour="inicio"]')?.classList.contains('driver-active-element')).toBe(true)
  })

  it('no abre nada si ningún paso queda visible', () => {
    preparar()
    const { abierto } = iniciar([{ titulo: 'Ausente', descripcion: '.', destino: 'no-existe' }])

    expect(abierto).toBe(false)
    expect(screen.getByText('Guía activa: ninguna')).toBeTruthy()
  })

  it('al desmontarse cierra el recorrido sin informar omisión', async () => {
    const { unmount } = preparar()
    const { onComplete, onSkip } = iniciar()
    await waitFor(() => expect(tituloActual()).toBe('Bienvenida'))

    unmount()

    expect(document.querySelector('.driver-popover')).toBeNull()
    expect(onSkip).not.toHaveBeenCalled()
    expect(onComplete).not.toHaveBeenCalled()
  })
})

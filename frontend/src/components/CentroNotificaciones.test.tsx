import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { type Notificacion, contarPendientes } from '../pages/notificaciones'
import { CentroNotificaciones } from './CentroNotificaciones'
import { adaptarNotificacion } from './notificaciones/avisos'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const notifJuridica: Notificacion = {
  id: 1,
  tipo: 'REVISION_JURIDICA_PENDIENTE',
  entidad_tipo: 'CONVENIO',
  entidad_id: 10,
  mensaje: 'El convenio CON-10 fue entregado a revisión jurídica.',
  leida: false,
  leida_en: null,
  resuelta: false,
  resuelta_en: null,
  creado_en: '2026-10-07T12:00:00Z',
}

const notifContraparteLeida: Notificacion = {
  id: 2,
  tipo: 'REVISION_CONTRAPARTE_PENDIENTE',
  entidad_tipo: 'CONVENIO',
  entidad_id: 20,
  mensaje: 'El convenio CON-20 está pendiente de revisión por la contraparte.',
  leida: true,
  leida_en: '2026-10-07T12:05:00Z',
  resuelta: false,
  resuelta_en: null,
  creado_en: '2026-10-07T11:00:00Z',
}

const notifSolicitudResuelta: Notificacion = {
  id: 3,
  tipo: 'SOLICITUD_DEVUELTA',
  entidad_tipo: 'SOLICITUD',
  entidad_id: 30,
  mensaje: 'Su solicitud fue devuelta con observaciones.',
  leida: true,
  leida_en: '2026-10-07T13:00:00Z',
  resuelta: true,
  resuelta_en: '2026-10-07T13:05:00Z',
  creado_en: '2026-10-07T10:00:00Z',
}

function renderizar(props: { notificaciones?: Notificacion[]; cargando?: boolean; error?: boolean } = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <CentroNotificaciones
          fuentes={[{
            categoria: 'acciones',
            avisos: (props.notificaciones ?? []).map(adaptarNotificacion),
            cargando: props.cargando ?? false,
            error: props.error ?? false,
          }]}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const notifResueltaNoLeida: Notificacion = {
  id: 4,
  tipo: 'DEVOLUCION_REVISION',
  entidad_tipo: 'CONVENIO',
  entidad_id: 40,
  mensaje: 'La revisión jurídica devolvió el convenio CON-40.',
  leida: false,
  leida_en: null,
  resuelta: true,
  resuelta_en: '2026-10-07T14:00:00Z',
  creado_en: '2026-10-07T09:00:00Z',
}

describe('CentroNotificaciones', () => {
  it('muestra el estado de carga', () => {
    renderizar({ cargando: true })
    expect(screen.getByText('Consultando notificaciones…')).toBeTruthy()
  })

  it('muestra el estado de error', () => {
    renderizar({ error: true })
    expect(
      screen.getByText('No fue posible consultar sus notificaciones.'),
    ).toBeTruthy()
  })

  it('muestra el estado vacío cuando no hay notificaciones', () => {
    renderizar({ notificaciones: [] })
    expect(screen.getByText('No tienes notificaciones pendientes')).toBeTruthy()
  })

  it('lista las notificaciones con su etiqueta y mensaje', () => {
    renderizar({ notificaciones: [notifJuridica, notifContraparteLeida] })

    expect(screen.getByText(notifJuridica.mensaje)).toBeTruthy()
    expect(screen.getByText(notifContraparteLeida.mensaje)).toBeTruthy()
    expect(screen.getByText('Revisión jurídica')).toBeTruthy()
    expect(screen.getByText('Revisión de contraparte')).toBeTruthy()
  })

  it('enlaza jurídica/devolución a la ficha del convenio', () => {
    renderizar({ notificaciones: [notifJuridica] })
    const item = screen.getByText(notifJuridica.mensaje).closest('li')!
    const enlace = within(item).getByRole('link', { name: 'Ver' }) as HTMLAnchorElement
    expect(enlace.getAttribute('href')).toBe('/convenios/10')
  })

  it('enlaza revisión de contraparte al listado de revisiones pendientes, no al convenio', () => {
    renderizar({ notificaciones: [notifContraparteLeida] })
    const item = screen.getByText(notifContraparteLeida.mensaje).closest('li')!
    const enlace = within(item).getByRole('link', { name: 'Ver' }) as HTMLAnchorElement
    expect(enlace.getAttribute('href')).toBe('/revisiones-contraparte')
  })

  it('enlaza solicitud devuelta a la solicitud propia', () => {
    renderizar({ notificaciones: [notifSolicitudResuelta] })
    const item = screen.getByText(notifSolicitudResuelta.mensaje).closest('li')!
    const enlace = within(item).getByRole('link', { name: 'Ver' }) as HTMLAnchorElement
    expect(enlace.getAttribute('href')).toBe('/solicitudes/30')
  })

  it('una notificación ya leída no muestra el botón de marcar como leída', () => {
    renderizar({ notificaciones: [notifContraparteLeida] })
    expect(
      screen.queryByRole('button', { name: 'Marcar como leída' }),
    ).toBeNull()
  })

  it('marcar como leída llama al PATCH correcto', async () => {
    // CentroNotificaciones recibe `notificaciones` por prop (quien la usa,
    // AppLayout, la mantiene sincronizada vía la query); por eso aquí solo
    // se verifica que dispare la llamada correcta, no que el prop cambie.
    const usuario = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...notifJuridica, leida: true }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderizar({ notificaciones: [notifJuridica] })

    await usuario.click(screen.getByRole('button', { name: 'Marcar como leída' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/notificaciones/1/leida',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })

  it('hacer clic en "Ver" de una notificación no leída también la marca como leída', async () => {
    const usuario = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...notifJuridica, leida: true }), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderizar({ notificaciones: [notifJuridica] })

    await usuario.click(screen.getByRole('link', { name: 'Ver' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/notificaciones/1/leida',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })

  it('hacer clic en "Ver" de una notificación ya leída no vuelve a llamar al PATCH', async () => {
    const usuario = userEvent.setup()
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    renderizar({ notificaciones: [notifContraparteLeida] })

    await usuario.click(screen.getByRole('link', { name: 'Ver' }))

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('una notificación resuelta muestra la etiqueta "Atendida"', () => {
    renderizar({ notificaciones: [notifSolicitudResuelta] })
    const item = screen.getByText(notifSolicitudResuelta.mensaje).closest('li')!
    expect(within(item).getByText('Atendida')).toBeTruthy()
  })

  it('una notificación pendiente no muestra "Atendida"', () => {
    renderizar({ notificaciones: [notifJuridica] })
    const item = screen.getByText(notifJuridica.mensaje).closest('li')!
    expect(within(item).queryByText('Atendida')).toBeNull()
  })

  it('"Atendida" y "leída" son conceptos independientes: una resuelta sin leer sigue ofreciendo marcarla como leída', () => {
    renderizar({ notificaciones: [notifResueltaNoLeida] })
    const item = screen.getByText(notifResueltaNoLeida.mensaje).closest('li')!
    expect(within(item).getByText('Atendida')).toBeTruthy()
    expect(
      within(item).getByRole('button', { name: 'Marcar como leída' }),
    ).toBeTruthy()
  })

  it('una notificación leída pero no resuelta no muestra "Atendida"', () => {
    renderizar({ notificaciones: [notifContraparteLeida] })
    const item = screen.getByText(notifContraparteLeida.mensaje).closest('li')!
    expect(within(item).queryByText('Atendida')).toBeNull()
  })
})

describe('contarPendientes', () => {
  it('cuenta solo las notificaciones no resueltas', () => {
    expect(
      contarPendientes([notifJuridica, notifContraparteLeida, notifSolicitudResuelta]),
    ).toBe(2)
  })

  it('una notificación resuelta no cuenta como pendiente aunque no esté leída', () => {
    const resueltaNoLeida: Notificacion = { ...notifSolicitudResuelta, leida: false }
    expect(contarPendientes([resueltaNoLeida])).toBe(0)
  })

  it('devuelve 0 cuando la lista todavía no cargó', () => {
    expect(contarPendientes(undefined)).toBe(0)
  })

  it('devuelve 0 con una lista vacía', () => {
    expect(contarPendientes([])).toBe(0)
  })
})

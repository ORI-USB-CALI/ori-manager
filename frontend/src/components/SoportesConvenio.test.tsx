import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { NotificationsContext } from '../app/notifications/useNotifications'
import type { SoporteConvenio } from '../pages/soportes'
import { SoportesConvenio } from './SoportesConvenio'

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const soportesEjemplo: SoporteConvenio[] = [
  {
    id: 1,
    nombre_original: 'acuerdo_firmado.pdf',
    tamano_bytes: 2048,
    fecha_creacion: '2026-10-10T14:30:00Z',
    usuario_nombre: 'Gestor ORI USB',
  },
  {
    id: 2,
    nombre_original: 'anexo_tecnico.pdf',
    tamano_bytes: 1572864, // 1.5 MB
    fecha_creacion: '2026-10-11T09:15:00Z',
    usuario_nombre: 'Administrador ORI',
  },
]

function renderizar(props: Partial<ComponentProps<typeof SoportesConvenio>> = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const notify = vi.fn()
  const resultado = render(
    <NotificationsContext.Provider value={notify}>
      <QueryClientProvider client={cliente}>
        <SoportesConvenio
          convenioId={10}
          estadoConvenio="VIGENTE"
          puedeGestionarSoportes={true}
          {...props}
        />
      </QueryClientProvider>
    </NotificationsContext.Provider>,
  )
  return { ...resultado, notify, cliente }
}

describe('SoportesConvenio (FE-02, CA-03: Visualización y descarga de soportes)', () => {
  it('renderiza la tabla con los documentos asociados y sus columnas correspondientes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => soportesEjemplo,
      }),
    )

    renderizar()

    await waitFor(() => {
      expect(screen.getByTestId('tabla-soportes')).toBeTruthy()
    })

    // Columnas de la tabla
    expect(screen.getByText('Documento')).toBeTruthy()
    expect(screen.getByText('Tamaño')).toBeTruthy()
    expect(screen.getByText('Fecha de carga')).toBeTruthy()
    expect(screen.getByText('Usuario responsable')).toBeTruthy()
    expect(screen.getByText('Acciones')).toBeTruthy()

    // Fila 1: acuerdo_firmado.pdf
    expect(screen.getByText('acuerdo_firmado.pdf')).toBeTruthy()
    expect(screen.getByText('2.0 KB')).toBeTruthy()
    expect(screen.getByText('Gestor ORI USB')).toBeTruthy()

    const btnVer1 = screen.getByTestId('btn-ver-soporte-1') as HTMLAnchorElement
    expect(btnVer1.getAttribute('href')).toBe(
      '/api/convenios/10/documentos/1/descargar?disposicion=inline',
    )
    expect(btnVer1.getAttribute('target')).toBe('_blank')

    const btnDescargar1 = screen.getByTestId('btn-descargar-soporte-1') as HTMLAnchorElement
    expect(btnDescargar1.getAttribute('href')).toBe(
      '/api/convenios/10/documentos/1/descargar?disposicion=attachment',
    )
    expect(btnDescargar1.getAttribute('download')).toBe('acuerdo_firmado.pdf')

    // Fila 2: anexo_tecnico.pdf
    expect(screen.getByText('anexo_tecnico.pdf')).toBeTruthy()
    expect(screen.getByText('1.5 MB')).toBeTruthy()
    expect(screen.getByText('Administrador ORI')).toBeTruthy()
  })

  it('muestra el estado vacío cuando no existen soportes adjuntos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [],
      }),
    )

    renderizar()

    await waitFor(() => {
      expect(
        screen.getByText('Aún no hay documentos de soporte asociados a este convenio'),
      ).toBeTruthy()
    })
    expect(screen.queryByTestId('tabla-soportes')).toBeNull()
  })
})

describe('SoportesConvenio (FE-03, CA-04: Control de visualización y accesos en UI)', () => {
  it('muestra el botón de carga cuando el usuario tiene permiso y el convenio está VIGENTE', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [],
      }),
    )

    renderizar({ estadoConvenio: 'VIGENTE', puedeGestionarSoportes: true })

    expect(screen.getByTestId('btn-cargar-soporte')).toBeTruthy()
    expect(screen.getByText('+ Cargar documento PDF')).toBeTruthy()
  })

  it('muestra el botón de carga cuando el usuario tiene permiso y el convenio está POR_VENCER', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [],
      }),
    )

    renderizar({ estadoConvenio: 'POR_VENCER', puedeGestionarSoportes: true })

    expect(screen.getByTestId('btn-cargar-soporte')).toBeTruthy()
  })

  it('oculta el botón de carga cuando el convenio no está activo (ej: EN_TRAMITE)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => soportesEjemplo,
      }),
    )

    renderizar({ estadoConvenio: 'EN_TRAMITE', puedeGestionarSoportes: true })

    // El botón de carga NO debe aparecer
    expect(screen.queryByTestId('btn-cargar-soporte')).toBeNull()

    // Pero la tabla sigue disponible en modo solo lectura
    await waitFor(() => {
      expect(screen.getByTestId('tabla-soportes')).toBeTruthy()
    })
  })

  it('oculta el botón de carga cuando el convenio está VENCIDO o FINALIZADO', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => soportesEjemplo,
      }),
    )

    renderizar({ estadoConvenio: 'FINALIZADO', puedeGestionarSoportes: true })

    expect(screen.queryByTestId('btn-cargar-soporte')).toBeNull()
  })

  it('no renderiza la sección si el usuario no tiene permisos sobre soportes', () => {
    renderizar({ puedeGestionarSoportes: false })

    expect(screen.queryByText('Documentos de soporte')).toBeNull()
    expect(screen.queryByTestId('btn-cargar-soporte')).toBeNull()
  })

  it('abre el modal de carga al hacer clic en el botón de carga', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [],
      }),
    )

    renderizar({ estadoConvenio: 'VIGENTE', puedeGestionarSoportes: true })

    const btnCargar = screen.getByTestId('btn-cargar-soporte')
    await user.click(btnCargar)

    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('Cargar documento soporte (PDF)')).toBeTruthy()
  })
})

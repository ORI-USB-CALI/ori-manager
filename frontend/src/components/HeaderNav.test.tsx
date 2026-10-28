import { act, cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { crearNavegacion } from '../app/navigation'
import { HeaderNav, type ElementoNav, type EnlaceNav } from './HeaderNav'

afterEach(() => {
  cleanup()
})

// Dos "roles" simulados: el conjunto de enlaces que AppLayout construiría
// con puede(...) para un Administrador (muchos permisos) y para un
// Solicitante (pocos). HeaderNav no decide esto — solo renderiza lo que
// recibe — así que probarlo aquí cubre "por rol" sin tener que mockear
// useSesion ni la sesión completa de AppLayout.
const enlacesAdministrador: EnlaceNav[] = [
  { to: '/', label: 'Inicio', end: true },
  { to: '/aliados', label: 'Aliados' },
  { to: '/convenios', label: 'Consulta de convenios' },
  { to: '/admin/usuarios', label: 'Usuarios' },
  { to: '/admin/bitacora', label: 'Bitácora' },
  { to: '/ori/solicitudes', label: 'Solicitudes recibidas' },
  { to: '/convenios/nuevo', label: 'Crear convenio manual' },
  { to: '/convenios/tablero', label: 'Tablero de convenios' },
  { to: '/renovaciones', label: 'Renovaciones' },
  { to: '/reportes/convenios-activos', label: 'Reportes' },
  { to: '/reportes/estadisticas-convenios', label: 'Estadísticas' },
  { to: '/revisiones-juridicas', label: 'Revisiones jurídicas' },
]

const enlacesSolicitante: EnlaceNav[] = [
  { to: '/', label: 'Inicio', end: true },
  { to: '/solicitudes', label: 'Mis solicitudes' },
]

function renderNav(enlaces: ElementoNav[], rutaInicial = '/') {
  return render(
    <MemoryRouter initialEntries={[rutaInicial]}>
      <Routes>
        <Route path="*" element={<HeaderNav enlaces={enlaces} />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('HeaderNav — por rol', () => {
  it('muestra únicamente los enlaces que le llegan para un Administrador', () => {
    renderNav(enlacesAdministrador)

    for (const enlace of enlacesAdministrador) {
      expect(screen.getByRole('link', { name: enlace.label })).toBeTruthy()
    }
    expect(screen.queryByRole('link', { name: 'Mis solicitudes' })).toBeNull()
  })

  it('muestra únicamente los enlaces que le llegan para un Solicitante', () => {
    renderNav(enlacesSolicitante)

    expect(screen.getByRole('link', { name: 'Mis solicitudes' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Usuarios' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Bitácora' })).toBeNull()
  })
})

describe('HeaderNav — secciones agrupadas', () => {
  const navegacion = crearNavegacion(() => true)

  it('agrupa Crear convenio manual y administración y conserva los enlaces existentes', async () => {
    renderNav(navegacion)
    const usuario = userEvent.setup()
    expect(navegacion.map(({ label }) => label)).toEqual([
      'Inicio', 'Aliados', 'Solicitudes', 'Convenios', 'Renovaciones', 'Reportes', 'Estadísticas', 'Administración',
    ])
    expect(screen.queryByRole('link', { name: 'Crear convenio manual' })).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Convenios' }))
    const grupo = screen.getByRole('button', { name: 'Convenios' }).parentElement!
    expect(within(grupo).getByRole('link', { name: 'Crear convenio manual' }).getAttribute('href')).toBe('/convenios/nuevo')
    expect(within(grupo).getByRole('link', { name: 'Revisiones jurídicas' })).toBeTruthy()
    await usuario.click(screen.getByRole('button', { name: 'Administración' }))
    expect(screen.queryByRole('link', { name: 'Crear convenio manual' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Usuarios' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Bitácora' })).toBeTruthy()
  })

  it.each([
    ['/convenios', 'Consulta de convenios'],
    ['/convenios/?pagina=2', 'Consulta de convenios'],
    ['/convenios/tablero', 'Tablero de convenios'],
    ['/convenios/tablero/', 'Tablero de convenios'],
    ['/convenios/nuevo', 'Crear convenio manual'],
    ['/convenios/42/historial', 'Consulta de convenios'],
    ['/revisiones-juridicas', 'Revisiones jurídicas'],
    ['/reportes/estadisticas-convenios', 'Estadísticas'],
    ['/admin/bitacora', 'Bitácora'],
    ['/ori/solicitudes/42/historial', 'Solicitudes recibidas'],
    ['/solicitudes/42', 'Mis solicitudes'],
  ])('activa solo %s → %s', (ruta, etiqueta) => {
    renderNav(navegacion, ruta)
    const activos = document.querySelectorAll('a[aria-current="page"]')
    expect(activos).toHaveLength(1)
    expect(activos[0].textContent).toBe(etiqueta)
  })

  it('omite grupos vacíos y solo incluye opciones autorizadas', async () => {
    renderNav(crearNavegacion((permiso) => permiso === 'solicitudes.ver_propias'))
    const usuario = userEvent.setup()
    expect(screen.queryByRole('button', { name: 'Convenios' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Administración' })).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Solicitudes' }))
    expect(screen.getByRole('link', { name: 'Mis solicitudes' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Solicitudes recibidas' })).toBeNull()
  })

  it('abre con teclado, recorre enlaces con Tab y Escape devuelve foco al grupo antes de cerrar el menú móvil', async () => {
    renderNav(navegacion)
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
    const boton = screen.getByRole('button', { name: 'Convenios' })
    boton.focus()
    await usuario.keyboard('{Enter}')
    expect(boton.getAttribute('aria-expanded')).toBe('true')
    expect(document.getElementById(boton.getAttribute('aria-controls')!)?.hidden).toBe(false)
    await usuario.tab()
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Consulta de convenios' }))
    await usuario.keyboard('{Escape}')
    expect(document.activeElement).toBe(boton)
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    await usuario.keyboard('{Escape}')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
  })

  it('cierra el submenú al salir con Tab y al hacer clic fuera', async () => {
    renderNav(navegacion)
    const usuario = userEvent.setup()
    const boton = screen.getByRole('button', { name: 'Administración' })
    await usuario.click(boton)
    screen.getByRole('link', { name: 'Bitácora' }).focus()
    await usuario.tab()
    expect(boton.getAttribute('aria-expanded')).toBe('false')
    await usuario.click(boton)
    await usuario.click(document.body)
    expect(boton.getAttribute('aria-expanded')).toBe('false')
  })

  it('cierra al elegir la ruta activa y al navegar con Atrás/Adelante', async () => {
    const router = createMemoryRouter([{ path: '*', element: <HeaderNav enlaces={navegacion} /> }], {
      initialEntries: ['/', '/convenios/tablero'],
    })
    render(<RouterProvider router={router} />)
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Convenios' }))
    await usuario.click(screen.getByRole('link', { name: 'Tablero de convenios' }))
    expect(screen.getByRole('button', { name: 'Convenios' }).getAttribute('aria-expanded')).toBe('false')
    await usuario.click(screen.getByRole('button', { name: 'Convenios' }))
    await act(() => router.navigate(-1))
    expect(screen.getByRole('button', { name: 'Convenios' }).getAttribute('aria-expanded')).toBe('false')
    expect(screen.getByRole('link', { name: 'Inicio' }).getAttribute('aria-current')).toBe('page')
    await act(() => router.navigate(1))
    expect(screen.getByRole('button', { name: 'Convenios' }).getAttribute('aria-expanded')).toBe('false')
    expect(document.querySelector('a[aria-current="page"]')?.textContent).toBe('Tablero de convenios')
  })
})

describe('HeaderNav — menú colapsable (operable con teclado)', () => {
  it('arranca cerrado y el botón alterna aria-expanded al abrir/cerrar', async () => {
    renderNav(enlacesAdministrador)
    const usuario = userEvent.setup()
    const boton = screen.getByRole('button', { name: 'Abrir menú de navegación' })
    expect(boton.getAttribute('aria-expanded')).toBe('false')

    await usuario.click(boton)
    expect(screen.getByRole('button', { name: 'Cerrar menú de navegación' }).getAttribute('aria-expanded')).toBe(
      'true',
    )

    await usuario.click(screen.getByRole('button', { name: 'Cerrar menú de navegación' }))
    expect(screen.getByRole('button', { name: 'Abrir menú de navegación' }).getAttribute('aria-expanded')).toBe(
      'false',
    )
  })

  it('Escape cierra el menú y devuelve el foco al botón', async () => {
    renderNav(enlacesAdministrador)
    const usuario = userEvent.setup()

    await usuario.click(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
    expect(screen.getByRole('button', { name: 'Cerrar menú de navegación' })).toBeTruthy()

    await usuario.keyboard('{Escape}')
    const botonCerrado = screen.getByRole('button', { name: 'Abrir menú de navegación' })
    expect(botonCerrado.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(botonCerrado)
  })

  it('un clic fuera del menú lo cierra', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <button type="button">Fuera</button>
        <Routes>
          <Route path="*" element={<HeaderNav enlaces={enlacesAdministrador} />} />
        </Routes>
      </MemoryRouter>,
    )
    const usuario = userEvent.setup()

    await usuario.click(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
    expect(screen.getByRole('button', { name: 'Cerrar menú de navegación' })).toBeTruthy()

    await usuario.click(screen.getByRole('button', { name: 'Fuera' }))
    expect(screen.getByRole('button', { name: 'Abrir menú de navegación' })).toBeTruthy()
  })

  it('el menú se cierra al navegar (clic en un enlace)', async () => {
    renderNav(enlacesAdministrador, '/')
    const usuario = userEvent.setup()

    await usuario.click(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
    expect(screen.getByRole('button', { name: 'Cerrar menú de navegación' })).toBeTruthy()

    await usuario.click(screen.getByRole('link', { name: 'Aliados' }))

    expect(screen.getByRole('button', { name: 'Abrir menú de navegación' })).toBeTruthy()
  })
})


describe('HeaderNav — regresiones HT-04', () => {
  it('todos los enlaces autorizados siguen disponibles al abrir el menú', async () => {
    renderNav(enlacesAdministrador)
    const usuario = userEvent.setup()
    const boton = screen.getByRole('button', { name: 'Abrir menú de navegación' })
    const idPanel = boton.getAttribute('aria-controls')
    expect(idPanel).toBeTruthy()
    expect(document.getElementById(idPanel!)?.getAttribute('aria-label')).toBe('Navegación principal')

    await usuario.click(boton)
    for (const enlace of enlacesAdministrador) {
      expect(screen.getByRole('link', { name: enlace.label })).toBeTruthy()
    }
  })

  it('cierra el menú al seleccionar la misma ruta activa', async () => {
    renderNav(enlacesAdministrador, '/')
    const usuario = userEvent.setup()
    await usuario.click(screen.getByRole('button', { name: 'Abrir menú de navegación' }))
    await usuario.click(screen.getByRole('link', { name: 'Inicio' }))
    expect(screen.getByRole('button', { name: 'Abrir menú de navegación' }).getAttribute('aria-expanded')).toBe('false')
  })

  it.each(['Solicitante Interno', 'Solicitante Externo'])(
    'solo muestra enlaces recibidos para %s (fixture representativa)', () => {
      renderNav(enlacesSolicitante)
      expect(screen.getByRole('link', { name: 'Mis solicitudes' })).toBeTruthy()
      expect(screen.queryByRole('link', { name: 'Usuarios' })).toBeNull()
      expect(screen.queryByRole('link', { name: 'Bitácora' })).toBeNull()
    },
  )
})

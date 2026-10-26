import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { HeaderNav, type EnlaceNav } from './HeaderNav'

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

function renderNav(enlaces: EnlaceNav[], rutaInicial = '/') {
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

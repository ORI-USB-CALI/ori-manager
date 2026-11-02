import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NotificationProvider } from '../app/notifications/Notifications'
import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { SolicitudPage } from './SolicitudPage'
import type { CatalogosSolicitud, Solicitud } from './solicitudes'

/** HT14-FE02: formatos incorrectos, corrección y reenvío, borradores incompletos y mensajes del backend. */
const CATALOGOS: CatalogosSolicitud = {
  solicitante: {
    tipo_usuario: 'EXTERNO', tipo_unidad: null, nombre: 'Carlos Pérez', correo: 'carlos@externo.com',
    identificacion: null, entidad: null, cargo: null, unidad: null, programa: null,
  },
  tipos_convenio: [{ id: 1, codigo: 'MARCO', nombre: 'Marco', naturaleza: 'MARCO' }],
  tipos_documento: [{ codigo: 'CAMARA_COMERCIO', nombre: 'Cámara de Comercio', es_representacion_legal: true }],
  requiere_documento_representacion: true,
}

const SESION: Sesion = {
  id: 9, correo: 'carlos@externo.com', nombre_completo: 'Carlos Pérez', activo: true, tipo_usuario: 'EXTERNO',
  rol: { codigo: 'SOLICITANTE_EXTERNO', nombre: 'Solicitante externo' },
  permisos: ['solicitudes.crear', 'solicitudes.ver_propias'],
}

const TEXTO_REQUERIDO = [
  'nombre_aliado_propuesto', 'correo_aliado_propuesto', 'ciudad_aliado_propuesto', 'telefono_aliado_propuesto',
  'direccion_aliado_propuesto', 'identificacion_aliado_propuesto', 'contacto_contraparte_nombre',
  'contacto_contraparte_cargo', 'contacto_contraparte_telefono', 'contacto_contraparte_correo', 'justificacion',
  'objeto', 'actividades_por_parte', 'metas_esperadas', 'implicacion_financiera', 'vigencia_estimada',
  'requisitos_renovacion', 'supervisor_usb_nombre', 'supervisor_usb_cargo', 'supervisor_usb_telefono',
  'supervisor_usb_correo', 'supervisor_contraparte_nombre', 'supervisor_contraparte_cargo',
  'supervisor_contraparte_telefono', 'supervisor_contraparte_correo', 'solicitante_documento', 'solicitante_entidad',
]

const DEVUELTA = {
  ...Object.fromEntries(TEXTO_REQUERIDO.map((campo) => [campo, 'Dato'])),
  id: 5, consecutivo: 'SOL-00000005', estado: 'DEVUELTA', tipo_solicitante: 'EXTERNO', solicitante_id: 9,
  solicitante_nombre: 'Carlos Pérez', solicitante_correo: 'carlos@externo.com', solicitante_tipo_documento: 'PASAPORTE',
  tipo_aliado_propuesto: 'UNIVERSIDAD', tipo_identificacion_aliado_propuesto: 'PASAPORTE',
  pais_aliado_propuesto_id: 1, tipo_convenio_id: 1, documentos: [],
} as unknown as Solicitud

type Respuesta = (metodo: string, url: string) => Response | undefined

function preparar(ruta: string, responder: Respuesta = () => undefined) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  cliente.setQueryData(CLAVE_SESION, SESION)
  const fetch = vi.fn(async (url: string, opciones?: RequestInit) => {
    const metodo = opciones?.method ?? 'GET'
    const respuesta = responder(metodo, url)
    if (respuesta) return respuesta
    if (url.endsWith('/solicitudes/catalogos')) return Response.json(CATALOGOS)
    if (url.endsWith('/paises')) return Response.json([{ id: 1, codigo_iso: 'CO', nombre: 'Colombia' }])
    return Response.json({ detail: 'No encontrado' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  render(
    <QueryClientProvider client={cliente}>
      <NotificationProvider>
        <MemoryRouter initialEntries={[ruta]}>
          <Routes>
            <Route path="/solicitudes/nueva" element={<SolicitudPage />} />
            <Route path="/solicitudes/:solicitudId" element={<SolicitudPage />} />
          </Routes>
        </MemoryRouter>
      </NotificationProvider>
    </QueryClientProvider>,
  )
  return fetch
}

function llamadas(fetch: ReturnType<typeof preparar>, metodo: string) {
  return fetch.mock.calls.filter(([, opciones]) => opciones?.method === metodo)
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('validación de formato en el formulario de solicitud (HT14-FE02)', () => {
  it('asocia el error al campo de forma accesible y lo retira al corregir (CA-07)', async () => {
    const user = userEvent.setup()
    preparar('/solicitudes/nueva')
    const telefono = await screen.findByRole('textbox', { name: 'Teléfono institucional *' })

    await user.type(telefono, 'abc')
    await user.tab()

    const error = await screen.findByText(/Ingrese un teléfono válido/)
    expect(telefono.getAttribute('aria-invalid')).toBe('true')
    expect(telefono.getAttribute('aria-describedby')).toBe(error.id)
    expect((telefono as HTMLInputElement).value).toBe('abc')

    await user.clear(telefono)
    await user.type(telefono, '+57 300 123 4567')
    await user.tab()

    await waitFor(() => expect(screen.queryByText(/Ingrese un teléfono válido/)).toBeNull())
    expect(telefono.getAttribute('aria-invalid')).toBe('false')
  })

  it('no marca ciudades ni direcciones con tildes o eñes (CA-03, CA-04)', async () => {
    const user = userEvent.setup()
    preparar('/solicitudes/nueva')

    await user.type(await screen.findByRole('textbox', { name: 'Ciudad *' }), 'Bogotá')
    await user.type(screen.getByRole('textbox', { name: 'Dirección *' }), 'Vereda El Peñón km 3')
    await user.tab()

    expect(screen.queryByText(/La ciudad debe tener/)).toBeNull()
    expect(screen.queryByText(/La dirección debe tener/)).toBeNull()
  })

  it('guarda un borrador incompleto sin exigir los obligatorios (CA-05)', async () => {
    const user = userEvent.setup()
    const fetch = preparar('/solicitudes/nueva', (metodo, url) => (
      metodo === 'POST' && url.endsWith('/solicitudes') ? Response.json({ ...DEVUELTA, estado: 'BORRADOR' }, { status: 201 }) : undefined
    ))

    await user.click(await screen.findByRole('button', { name: 'Guardar borrador' }))

    expect(await screen.findByText('Borrador guardado.')).toBeTruthy()
    expect(llamadas(fetch, 'POST')).toHaveLength(1)
  })

  it('muestra el mensaje del backend en su campo, conserva lo escrito y permite reenviar (CA-06, CA-07)', async () => {
    const user = userEvent.setup()
    let intentos = 0
    preparar('/solicitudes/nueva', (metodo, url) => {
      if (metodo !== 'POST' || !url.endsWith('/solicitudes')) return undefined
      intentos += 1
      return intentos === 1
        ? Response.json({ detail: { message: 'La solicitud tiene datos con formato inválido', errors: { telefono_aliado_propuesto: 'Número rechazado por el servidor' } } }, { status: 422 })
        : Response.json({ ...DEVUELTA, estado: 'BORRADOR' }, { status: 201 })
    })
    const telefono = await screen.findByRole('textbox', { name: 'Teléfono institucional *' })
    const ciudad = screen.getByRole('textbox', { name: 'Ciudad *' })
    await user.type(telefono, '300 000')
    await user.type(ciudad, 'Cali')

    await user.click(screen.getByRole('button', { name: 'Guardar borrador' }))

    expect(await screen.findByText('Número rechazado por el servidor')).toBeTruthy()
    expect(telefono.getAttribute('aria-invalid')).toBe('true')
    expect((telefono as HTMLInputElement).value).toBe('300 000')
    expect((ciudad as HTMLInputElement).value).toBe('Cali')

    await user.clear(telefono)
    await user.type(telefono, '3001234567')
    await user.click(screen.getByRole('button', { name: 'Guardar borrador' }))

    expect(await screen.findByText('Borrador guardado.')).toBeTruthy()
    await waitFor(() => expect(screen.queryByText('Número rechazado por el servidor')).toBeNull())
    expect(intentos).toBe(2)
  })

  it('una devuelta rechazada al volver a radicar sigue editable y señala el campo (RN-09)', async () => {
    const user = userEvent.setup()
    preparar('/solicitudes/5', (metodo, url) => {
      if (url.endsWith('/solicitudes/5') && (metodo === 'GET' || metodo === 'PATCH')) return Response.json(DEVUELTA)
      if (metodo === 'POST' && url.endsWith('/solicitudes/5/radicar')) {
        return Response.json({ detail: { message: 'La solicitud está incompleta', errors: { direccion_aliado_propuesto: 'Dirección rechazada por el servidor' } } }, { status: 422 })
      }
      return undefined
    })

    await user.click(await screen.findByRole('button', { name: 'Volver a radicar' }))

    expect(await screen.findByText('Dirección rechazada por el servidor')).toBeTruthy()
    expect(screen.getByRole('textbox', { name: /^Dirección \*/ }).getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByText('Estado: DEVUELTA')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Volver a radicar' })).toBeTruthy()
  })

  it.each(['telefono_aliado_propuesto', 'contacto_contraparte_telefono', 'supervisor_usb_telefono', 'supervisor_contraparte_telefono'])(
    'H-01: permite editar y guardar %s canónico sin perder su extensión', async (campo) => {
      const user = userEvent.setup()
      const canonico = '+576025551234;ext=000123'
      const guardada = { ...DEVUELTA, [campo]: canonico }
      const fetch = preparar('/solicitudes/5', (metodo, url) => (
        url.endsWith('/solicitudes/5') && ['GET', 'PATCH'].includes(metodo) ? Response.json(guardada) : undefined
      ))
      await screen.findByRole('button', { name: 'Guardar cambios' })
      const telefono = document.querySelector(`[name="${campo}"]`) as HTMLInputElement
      await user.click(telefono)
      await user.tab()
      expect(telefono.getAttribute('aria-invalid')).toBe('false')
      expect(telefono.value).toBe(canonico)
      await user.click(screen.getByRole('button', { name: 'Guardar cambios' }))
      await screen.findByText('Borrador guardado.')
      expect(JSON.parse(String(llamadas(fetch, 'PATCH')[0][1]?.body))[campo]).toBe(canonico)
    },
  )

  it('valida la sintaxis del DV aunque el borrador aún no tenga la base', async () => {
    const user = userEvent.setup()
    preparar('/solicitudes/nueva')
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Tipo de documento *' }), 'NIT')
    const dv = screen.getByLabelText('Dígito de verificación *')
    await user.type(dv, 'A')
    await user.tab()
    expect(dv.getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByText('El dígito de verificación debe ser un solo dígito')).toBeTruthy()
  })

  it.each([['Ciudad *', '\ufeffCali'], ['Dirección *', '\ufeffCasa 1']])(
    'H-06: no oculta caracteres de formato en %s antes de validar', async (etiqueta, valor) => {
      preparar('/solicitudes/nueva')
      const campo = await screen.findByRole('textbox', { name: etiqueta })
      fireEvent.change(campo, { target: { value: valor } })
      fireEvent.blur(campo)
      expect(campo.getAttribute('aria-invalid')).toBe('true')
      expect((campo as HTMLInputElement).value).toBe(valor)
    },
  )

  it.each([
    ['ciudad_aliado_propuesto', 'Ciudad *', 'e\u0301'.repeat(120), 'é'.repeat(120)],
    ['direccion_aliado_propuesto', 'Dirección *', 'e\u0301'.repeat(199) + '1', 'é'.repeat(199) + '1'],
  ])('H-06: envía %s en su forma canónica sin alterar lo escrito', async (nombre, etiqueta, valor, canonico) => {
    const fetch = preparar('/solicitudes/nueva', (metodo, url) => (
      metodo === 'POST' && url.endsWith('/solicitudes')
        ? Response.json({ ...DEVUELTA, estado: 'BORRADOR', [nombre]: canonico }, { status: 201 }) : undefined
    ))
    const campo = await screen.findByRole('textbox', { name: etiqueta })
    fireEvent.change(campo, { target: { value: valor } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
    await screen.findByText('Borrador guardado.')
    expect(JSON.parse(String(llamadas(fetch, 'POST')[0][1]?.body))[nombre]).toBe(canonico)
  })

  for (const control of ['\u0085', '\u001c', '\ufeff']) {
    it.each([
      ['identificacion_aliado_propuesto', '900123456'], ['solicitante_documento', '900123456'],
      ['digito_verificacion_aliado_propuesto', '8'], ['solicitante_digito_verificacion', '8'],
      ['telefono_aliado_propuesto', '6025551234'], ['contacto_contraparte_telefono', '6025551234'],
      ['supervisor_usb_telefono', '6025551234'], ['supervisor_contraparte_telefono', '6025551234'],
    ])(`H-07: %s no oculta U+${control.codePointAt(0)?.toString(16)} al validar ni enviar`, async (nombre, valor) => {
      const fetch = preparar('/solicitudes/nueva', (metodo, url) => (
        metodo === 'POST' && url.endsWith('/solicitudes')
          ? Response.json({ detail: { message: 'Formato inválido', errors: { [nombre]: 'Corrija este campo' } } }, { status: 422 }) : undefined
      ))
      await userEvent.setup().selectOptions(await screen.findByRole('combobox', { name: 'Tipo de identificación *' }), 'NIT')
      await userEvent.setup().selectOptions(screen.getByRole('combobox', { name: 'Tipo de documento *' }), 'NIT')
      for (const base of ['identificacion_aliado_propuesto', 'solicitante_documento']) {
        fireEvent.change(document.querySelector(`[name="${base}"]`) as HTMLInputElement, { target: { value: '900123456' } })
      }
      const campo = document.querySelector(`[name="${nombre}"]`) as HTMLInputElement
      const original = control + valor + control
      fireEvent.change(campo, { target: { value: original } })
      fireEvent.blur(campo)
      expect(campo.getAttribute('aria-invalid')).toBe('true')
      expect(campo.value).toBe(original)
      fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }))
      await screen.findByText('Corrija este campo')
      expect(JSON.parse(String(llamadas(fetch, 'POST')[0][1]?.body))[nombre]).toBe(original)
    })
  }
})

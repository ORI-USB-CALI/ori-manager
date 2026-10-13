import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import type { HistorialConvenio, ObservacionRevision } from '../pages/epica02'
import { HistorialConvenioContenido } from './HistorialConvenioContenido'

const gestor = { id: 1, nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' }
const contraparte = { id: 2, nombre_completo: 'Solicitante', correo: 'solicitante@example.com' }
const observacion: ObservacionRevision = {
  id: 100, origen: 'CONTRAPARTE', descripcion: 'Precisar las obligaciones de la Universidad',
  estado: 'ATENDIDA', respuesta: 'Se especificaron las obligaciones',
  registrada_por: contraparte, responsable: gestor, atendida_por: gestor,
  creado_en: '2026-10-01T14:00:00Z', fecha_atencion: '2026-10-02T15:00:00Z',
}

function preparar(datos: ObservacionRevision) {
  const historial: HistorialConvenio = {
    revisiones: [{
      id: 10, tipo: 'CONTRAPARTE', instancia_juridica: null, numero_ronda: null,
      estado: 'RESUELTA', resultado: 'DEVUELTA',
      version_convenio_id: null, version_resultado_id: null, version_convenio: null,
      version_resultado: null, snapshot_datos: null, creada_por: gestor,
      responsable: null, resuelta_por: null, resuelta_en: '2026-10-01T14:00:00Z',
      creado_en: '2026-10-01T12:00:00Z', observaciones: [datos],
      invitaciones_contraparte: [], respuesta_contraparte: null,
    }],
    cambios_etapa: [],
  }
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith('/revisiones') ? historial : url.endsWith('/linea-tiempo') ? [{
      codigo: 'ACTIVACION', nombre: 'Activación', estado: 'PENDIENTE', fecha: null,
    }] : { detail: 'Not Found' },
  ), { status: url.endsWith('/revisiones') || url.endsWith('/linea-tiempo') ? 200 : 404, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const sesion: Sesion = {
    ...gestor, activo: true, tipo_usuario: 'INTERNO',
    rol: { codigo: 'GESTOR_ORI', nombre: 'Gestor ORI' }, permisos: ['convenios.ver'],
  }
  cliente.setQueryData(CLAVE_SESION, sesion)
  render(
    <QueryClientProvider client={cliente}>
      <HistorialConvenioContenido convenioId={41} solicitudId={null} />
    </QueryClientProvider>,
  )
  return fetch
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('HT-03 observaciones y respuestas en el historial actual', () => {
  it('identifica la observación, su estado y el bloque separado de respuesta con responsable y fecha', async () => {
    preparar(observacion)
    const tarjeta = await screen.findByRole('article', { name: 'Observación #100' })
    expect(within(tarjeta).getByText('Precisar las obligaciones de la Universidad')).toBeTruthy()
    expect(within(tarjeta).getByText('Atendida')).toBeTruthy()
    expect(within(tarjeta).getByText('Responsable: Gestor ORI')).toBeTruthy()
    expect(within(tarjeta).getByText(`Registrada por Solicitante · ${new Date(observacion.creado_en).toLocaleString()}`)).toBeTruthy()
    const respuesta = within(tarjeta).getByRole('group', { name: 'Respuesta a la observación #100' })
    expect(within(respuesta).getByText('Se especificaron las obligaciones')).toBeTruthy()
    expect(within(respuesta).getByText(`Gestor ORI · ${new Date(observacion.fecha_atencion!).toLocaleString()}`)).toBeTruthy()
    expect(within(respuesta).queryByText(observacion.descripcion)).toBeNull()
  })

  it('muestra la respuesta pendiente sin inventar un responsable y conserva el historial manual sin solicitud', async () => {
    const fetch = preparar({
      ...observacion, respuesta: null, estado: 'PENDIENTE',
      registrada_por: null, responsable: null, atendida_por: null, fecha_atencion: null,
    })
    const tarjeta = await screen.findByRole('article', { name: 'Observación #100' })
    expect(within(tarjeta).getByText('Pendiente')).toBeTruthy()
    const respuesta = within(tarjeta).getByRole('group', { name: 'Respuesta a la observación #100' })
    expect(within(respuesta).getByText('Pendiente de respuesta')).toBeTruthy()
    expect(within(respuesta).queryByText(/Gestor|Solicitante|Usuario no identificado|Contraparte externa/)).toBeNull()
    expect(within(respuesta).queryByRole('time')).toBeNull()
    expect(screen.getByRole('region', { name: 'Observaciones jurídicas' })).toBeTruthy()
    expect(await within(screen.getByRole('region', { name: 'Línea de tiempo' })).findByText('Activación')).toBeTruthy()
    expect(fetch.mock.calls.some(([url]) => url.includes('/solicitudes/'))).toBe(false)
  })

  it('conserva una respuesta histórica aunque no tenga autor ni fecha de atención', async () => {
    preparar({ ...observacion, atendida_por: null, fecha_atencion: null })
    const tarjeta = await screen.findByRole('article', { name: 'Observación #100' })
    const respuesta = within(tarjeta).getByRole('group', { name: 'Respuesta a la observación #100' })
    expect(within(respuesta).getByText('Se especificaron las obligaciones')).toBeTruthy()
    expect(respuesta.textContent).toBe('↳ RespuestaSe especificaron las obligaciones')
  })
})

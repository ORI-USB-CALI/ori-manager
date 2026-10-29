import { afterEach, describe, expect, it, vi } from 'vitest'

import { actualizarGuia, consultarGuia } from './estadoGuias'

const respuestaGuia = {
  guia: 'ONBOARDING_INICIAL',
  estado: 'PENDIENTE',
  version: null,
  actualizado_en: null,
}

afterEach(() => { vi.unstubAllGlobals() })

describe('HU-38 FE-03: API autenticada de guías', () => {
  it('consulta el estado de la guía asociada a la sesión sin enviar identificador de usuario', async () => {
    const fetchSimulado = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => respuestaGuia,
    })
    vi.stubGlobal('fetch', fetchSimulado)

    expect(await consultarGuia('ONBOARDING_INICIAL')).toEqual(respuestaGuia)
    expect(fetchSimulado).toHaveBeenCalledWith('/api/guias/ONBOARDING_INICIAL', expect.objectContaining({ credentials: 'include' }))
  })

  it('envía solo estado final y versión al completar', async () => {
    const fetchSimulado = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ ...respuestaGuia, estado: 'COMPLETADO', version: 1 }),
    })
    vi.stubGlobal('fetch', fetchSimulado)
    await actualizarGuia('ONBOARDING_INICIAL', 'COMPLETADO', 1)
    const [, opciones] = fetchSimulado.mock.calls[0]
    expect(opciones.method).toBe('PUT')
    expect(JSON.parse(opciones.body)).toEqual({ estado: 'COMPLETADO', version: 1 })
    expect(opciones.credentials).toBe('include')
  })
})

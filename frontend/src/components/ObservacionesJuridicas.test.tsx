import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ObservacionRevision, RevisionConvenioTrazabilidad, UsuarioResumen } from '../pages/epica02'
import { ObservacionesJuridicas } from './ObservacionesJuridicas'
import { formatDateTime } from './tableFormatters'

const revisor: UsuarioResumen = { id: 2, nombre_completo: 'Revisora Jurídica', correo: 'revisora@example.com' }
const segundoRevisor: UsuarioResumen = { id: 3, nombre_completo: 'Segundo Revisor', correo: 'revisor2@example.com' }
const gestor: UsuarioResumen = { id: 1, nombre_completo: 'Gestor ORI', correo: 'gestor@example.com' }

// Testing Library compara el texto con los espacios normalizados, y el formato de
// fecha de es-CO puede traer espacios no separables.
function autoria(nombre: string, fecha: string): string {
  return `${nombre} · ${formatDateTime(fecha)}`.replace(/\s+/g, ' ')
}

function observacion(datos: Partial<ObservacionRevision> & Pick<ObservacionRevision, 'id' | 'descripcion'>): ObservacionRevision {
  return {
    origen: 'REVISOR_ORI',
    respuesta: null,
    estado: 'PENDIENTE',
    registrada_por: revisor,
    responsable: gestor,
    atendida_por: null,
    fecha_atencion: null,
    creado_en: '2026-10-01T15:00:00Z',
    ...datos,
  }
}

function revision(
  datos: Partial<RevisionConvenioTrazabilidad> & Pick<RevisionConvenioTrazabilidad, 'id'>,
): RevisionConvenioTrazabilidad {
  return {
    version_convenio_id: null,
    version_resultado_id: null,
    version_convenio: null,
    version_resultado: null,
    instancia_juridica: 1,
    numero_ronda: 1,
    tipo: 'JURIDICA',
    estado: 'RESUELTA',
    resultado: 'DEVUELTA',
    responsable: null,
    creada_por: gestor,
    resuelta_por: revisor,
    snapshot_datos: null,
    creado_en: '2026-10-01T14:00:00Z',
    resuelta_en: '2026-10-01T15:00:00Z',
    observaciones: [],
    invitaciones_contraparte: [],
    respuesta_contraparte: null,
    ...datos,
  }
}

const historial: RevisionConvenioTrazabilidad[] = [
  revision({
    id: 10,
    observaciones: [
      observacion({
        id: 100,
        descripcion: 'Precisar el objeto del convenio',
        estado: 'ATENDIDA',
        respuesta: 'Objeto precisado con las actividades',
        atendida_por: gestor,
        fecha_atencion: '2026-10-02T13:30:00Z',
      }),
      observacion({ id: 101, descripcion: 'Ajustar la vigencia', creado_en: '2026-10-01T15:05:00Z' }),
    ],
  }),
  revision({ id: 11, tipo: 'CONTRAPARTE', instancia_juridica: null, numero_ronda: null, observaciones: [
    observacion({ id: 102, origen: 'CONTRAPARTE', descripcion: 'Observación de la contraparte' }),
  ] }),
  revision({ id: 12, numero_ronda: 2, resultado: 'APROBADA' }),
  revision({
    id: 13,
    numero_ronda: 2,
    instancia_juridica: 2,
    resuelta_por: segundoRevisor,
    observaciones: [
      observacion({
        id: 103,
        descripcion: 'Revisar la cláusula de confidencialidad',
        registrada_por: segundoRevisor,
        creado_en: '2026-10-05T09:00:00Z',
      }),
    ],
  }),
]

afterEach(cleanup)

describe('ObservacionesJuridicas', () => {
  it('agrupa las observaciones por ronda y por revisión jurídica sin mezclarlas', () => {
    render(<ObservacionesJuridicas revisiones={historial} />)

    const rondas = screen.getAllByRole('heading', { level: 3 }).map((titulo) => titulo.textContent)
    expect(rondas).toEqual(['Ronda 1', 'Ronda 2'])

    const [ronda1, ronda2] = Array.from(document.querySelectorAll<HTMLElement>('.ronda-juridica'))
    const instanciasRonda1 = within(ronda1).getAllByRole('article')
    expect(instanciasRonda1).toHaveLength(1)
    expect(within(instanciasRonda1[0]).getByRole('heading', { level: 4 }).textContent).toContain('Revisión jurídica 1 de 2')
    expect(within(instanciasRonda1[0]).getAllByRole('listitem').map((item) => item.querySelector('.observacion-juridica p')?.textContent))
      .toEqual(['Precisar el objeto del convenio', 'Ajustar la vigencia'])

    const [rj1Ronda2, rj2Ronda2] = within(ronda2).getAllByRole('article')
    expect(within(rj1Ronda2).getByText('Aprobada sin observaciones.')).toBeTruthy()
    expect(within(rj2Ronda2).getByRole('heading', { level: 4 }).textContent).toContain('Revisión jurídica 2 de 2')
    expect(within(rj2Ronda2).getByText('Revisar la cláusula de confidencialidad')).toBeTruthy()

    expect(screen.queryByText('Observación de la contraparte')).toBeNull()
  })

  it('muestra el revisor que registró cada observación y su fecha', () => {
    render(<ObservacionesJuridicas revisiones={historial} />)

    expect(screen.getAllByText(autoria('Revisora Jurídica', '2026-10-01T15:00:00Z'))).toHaveLength(1)
    expect(screen.getByText(autoria('Segundo Revisor', '2026-10-05T09:00:00Z'))).toBeTruthy()
  })

  it('relaciona la observación original con la corrección del Gestor', () => {
    render(<ObservacionesJuridicas revisiones={historial} />)

    const [atendida, pendiente] = screen.getAllByRole('listitem')
    expect(within(atendida).getByText('Precisar el objeto del convenio')).toBeTruthy()
    expect(within(atendida).getByText('Objeto precisado con las actividades')).toBeTruthy()
    expect(within(atendida).getByText(autoria('Gestor ORI', '2026-10-02T13:30:00Z'))).toBeTruthy()
    expect(within(atendida).getByText('Atendida')).toBeTruthy()

    expect(within(pendiente).getByText('Ajustar la vigencia')).toBeTruthy()
    expect(within(pendiente).getByText('Pendiente de atención')).toBeTruthy()
    expect(within(pendiente).getByText('Pendiente')).toBeTruthy()
  })

  it('indica cuando el convenio no tiene observaciones jurídicas', () => {
    render(<ObservacionesJuridicas revisiones={[revision({ id: 20, resultado: 'APROBADA' })]} />)

    expect(screen.getByText('Este convenio no tiene observaciones jurídicas registradas.')).toBeTruthy()
    expect(screen.queryByRole('article')).toBeNull()
  })
})

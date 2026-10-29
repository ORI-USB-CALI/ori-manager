import { afterEach, describe, expect, it } from 'vitest'

import type { CodigoRol } from '../auth/sesion'
import { pasosVisibles } from '../components/recorrido'
import { DESTINOS_SECCIONES_SOLICITUD, PASOS_SECCIONES_SOLICITUD } from './guiaRadicacion'

const SECCIONES = [
  '1. Información del solicitante',
  '2. Información de la contraparte',
  '3. Contacto de contraparte',
  '4. Información del convenio',
  '5. Supervisor o encargado de ejecución USB',
  '6. Supervisor o encargado de ejecución de la contraparte',
  '7. Documentación',
  '8. Observaciones adicionales',
]

function sesion(rol: CodigoRol) {
  return { rol: { codigo: rol, nombre: rol }, permisos: [] }
}

// Marca en el documento las ocho secciones, como hará SolicitudPage (FE01).
function montarSecciones(destinos: string[] = Object.values(DESTINOS_SECCIONES_SOLICITUD)) {
  for (const destino of destinos) {
    const seccion = document.createElement('section')
    seccion.dataset.tour = destino
    // jsdom no calcula diseño: se simula que la sección es visible.
    seccion.getClientRects = () => [{}] as unknown as DOMRectList
    document.body.append(seccion)
  }
}

function titulos(rol: CodigoRol) {
  return pasosVisibles(PASOS_SECCIONES_SOLICITUD, sesion(rol)).map((paso) => paso.popover?.title)
}

function descripcion(rol: CodigoRol, titulo: string) {
  return pasosVisibles(PASOS_SECCIONES_SOLICITUD, sesion(rol))
    .find((paso) => paso.popover?.title === titulo)?.popover?.description ?? ''
}

afterEach(() => { document.body.innerHTML = '' })

describe('pasos de las secciones de la solicitud (HU-39 FE02)', () => {
  it.each<CodigoRol>(['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'])(
    'cubre las ocho secciones en el orden del formulario para %s (CA-02)',
    (rol) => {
      montarSecciones()
      expect(titulos(rol)).toEqual(SECCIONES)
    },
  )

  it('cada paso apunta a una sección conocida y tiene contenido', () => {
    const destinos = new Set<string>(Object.values(DESTINOS_SECCIONES_SOLICITUD))
    for (const paso of PASOS_SECCIONES_SOLICITUD) {
      expect(destinos.has(paso.destino ?? '')).toBe(true)
      expect(paso.descripcion.length).toBeGreaterThan(40)
    }
    expect(new Set(PASOS_SECCIONES_SOLICITUD.map((paso) => paso.destino))).toEqual(destinos)
  })

  it('al solicitante interno le explica su unidad y cargo, sin campos del externo (CA-03)', () => {
    montarSecciones()
    const texto = descripcion('SOLICITANTE_INTERNO', SECCIONES[0])
    expect(texto).toContain('Facultad o Dependencia')
    expect(texto).toContain('cargo')
    expect(texto).not.toContain('tipo de documento')
    expect(texto).not.toContain('Empresa o Entidad')
  })

  it('al solicitante externo le explica el documento y el DV, sin campos del interno (CA-03)', () => {
    montarSecciones()
    const texto = descripcion('SOLICITANTE_EXTERNO', SECCIONES[0])
    expect(texto).toContain('tipo de documento')
    expect(texto).toContain('dígito de verificación')
    expect(texto).toContain('Empresa o Entidad')
    expect(texto).not.toContain('Facultad')
  })

  it.each<CodigoRol>(['ADMINISTRADOR_ORI', 'GESTOR_ORI', 'REVISOR_ORI'])(
    'no muestra instrucciones del solicitante a %s (CA-03)',
    (rol) => {
      montarSecciones()
      expect(titulos(rol)).not.toContain(SECCIONES[0])
    },
  )

  it('explica la documentación con las reglas actuales (CA-05)', () => {
    montarSecciones()
    const texto = descripcion('SOLICITANTE_EXTERNO', '7. Documentación')
    for (const regla of ['tipo de documento', 'PDF', 'JPG', 'PNG', '10 MB', 'al menos un documento de representación legal']) {
      expect(texto).toContain(regla)
    }
    for (const documento of ['Cámara de Comercio', 'RUT', 'Cédula del representante legal', 'Otro documento de representación legal']) {
      expect(texto).toContain(documento)
    }
    expect(texto).toContain('no reemplaza')
  })

  it('usa las mismas reglas de formato de HT-14', () => {
    montarSecciones()
    const contraparte = descripcion('SOLICITANTE_INTERNO', SECCIONES[1])
    expect(contraparte).toContain('sin el dígito de verificación')
    expect(contraparte).toContain('+34 912 345 678')
    expect(contraparte).toContain('urbanos, rurales e internacionales')
  })

  it('omite las secciones que no estén en la página', () => {
    montarSecciones([DESTINOS_SECCIONES_SOLICITUD.solicitante, DESTINOS_SECCIONES_SOLICITUD.documentacion])
    expect(titulos('SOLICITANTE_EXTERNO')).toEqual([SECCIONES[0], '7. Documentación'])
  })

  it('no explica las acciones, que corresponden a HU-39 FE03', () => {
    for (const paso of PASOS_SECCIONES_SOLICITUD) {
      expect(paso.descripcion).not.toMatch(/Guardar borrador|Radicar solicitud|Mis solicitudes/)
    }
  })
})

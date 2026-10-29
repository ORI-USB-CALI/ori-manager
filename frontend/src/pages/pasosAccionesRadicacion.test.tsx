import { describe, expect, it } from 'vitest'
import { crearPasosAccionesRadicacion } from './pasosAccionesRadicacion'

describe('HU-39 FE-03: acciones y seguimiento de radicación', () => {
  it('explica las acciones al final del recorrido', () => {
    const pasos = crearPasosAccionesRadicacion()
    expect(pasos.map((paso) => paso.titulo)).toEqual([
      'Adjuntar documentos',
      'Guardar borrador',
      'Radicar la solicitud',
      'Cómo corregir errores de validación',
      'Consultar Mis solicitudes',
    ])
  })

  it('usa los destinos del formulario existente para documentación y botones', () => {
    const pasos = crearPasosAccionesRadicacion()
    expect(pasos.slice(0, 3).map((paso) => paso.destino)).toEqual([
      'solicitud-documentacion',
      'solicitud-guardar-borrador',
      'solicitud-radicar',
    ])
  })

  it('explica los requisitos de los documentos sin cargarlos', () => {
    const paso = crearPasosAccionesRadicacion()[0]
    expect(paso.descripcion).toMatch(/PDF, JPG o PNG/)
    expect(paso.descripcion).toMatch(/10 MB/)
    expect(paso.descripcion).toMatch(/representación legal/)
    expect(paso.descripcion).toMatch(/no carga archivos/)
  })

  it('diferencia guardar de radicar y no promete ejecutarlos', () => {
    const pasos = crearPasosAccionesRadicacion()
    expect(pasos[1].descripcion).toContain('sin radicarla')
    expect(pasos[2].descripcion).toContain('no la ejecuta')
  })

  it('orienta ante errores de campos y formatos', () => {
    const pasos = crearPasosAccionesRadicacion()
    const texto = pasos[3].descripcion
    expect(texto).toMatch(/mensaje junto al campo/)
    expect(texto).toMatch(/teléfono/)
    expect(texto).toMatch(/dígito de verificación/)
  })

  it('incluye devoluciones solo si la solicitud está devuelta', () => {
    const normal = crearPasosAccionesRadicacion()
    const devuelta = crearPasosAccionesRadicacion(true)
    expect(normal.some((paso) => paso.titulo.includes('devuelta'))).toBe(false)
    expect(devuelta.some((paso) => paso.titulo === 'Corregir una solicitud devuelta')).toBe(true)
    expect(devuelta[4].descripcion).toContain('Volver a radicar')
    expect(devuelta[5].titulo).toBe('Consultar Mis solicitudes')
  })

  it('indica cómo regresar a Mis solicitudes, sin navegación automática', () => {
    const ultimo = crearPasosAccionesRadicacion().at(-1)
    expect(ultimo?.descripcion).toContain('Volver')
    expect(ultimo?.descripcion).toContain('no cambia de página')
  })

  it('devuelve copias independientes para no mezclar las aperturas del recorrido', () => {
    const primera = crearPasosAccionesRadicacion()
    primera[0].titulo = 'Modificado temporalmente'
    const segunda = crearPasosAccionesRadicacion()
    expect(segunda[0].titulo).toBe('Adjuntar documentos')
  })
})

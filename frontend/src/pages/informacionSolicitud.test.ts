import { describe, expect, it } from 'vitest'

// Contrato compartido con las pruebas API y de exportación del backend.
import ejemplo from '../../../backend/tests/fixtures/hu12_base_solicitud.json'
import { documentoTieneTexto, informacionSolicitudComoDocumento } from './informacionSolicitud'

describe('información narrativa opcional de solicitud', () => {
  it('recupera los cuatro campos sin introducir tipo, duración, vigencia ni variables', () => {
    const original = structuredClone(ejemplo.solicitud)
    const documento = informacionSolicitudComoDocumento(ejemplo.solicitud)
    expect(documento).toEqual(ejemplo.documento)
    expect(JSON.stringify(documento)).not.toMatch(/\{\{|\}\}|36|Tipo propuesto|Información de origen|PROYECTO DE CONVENIO/)
    expect(ejemplo.solicitud).toEqual(original)
  })

  it('omite campos vacíos y conserva texto especial como texto editable', () => {
    const documento = informacionSolicitudComoDocumento({
      objeto: '  <script> & texto\r\n\r\nOtro párrafo ', justificacion: '  ', actividades_por_parte: null, metas_esperadas: null,
    })
    expect(documento).toEqual({ type: 'doc', content: [
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Objeto propuesto' }] },
      { type: 'paragraph', content: [{ type: 'text', text: '<script> & texto' }] },
      { type: 'paragraph' },
      { type: 'paragraph', content: [{ type: 'text', text: 'Otro párrafo' }] },
    ] })
  })

  it('no fabrica contenido cuando faltan los campos narrativos', () => {
    expect(informacionSolicitudComoDocumento({ objeto: null, justificacion: '', actividades_por_parte: '  ', metas_esperadas: null })).toBeNull()
  })

  it('reconoce contenido previo en listas y no exige confirmar un documento vacío', () => {
    expect(documentoTieneTexto({ type: 'doc', content: [{ type: 'paragraph' }] })).toBe(false)
    expect(documentoTieneTexto({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '  ' }] }] })).toBe(false)
    expect(documentoTieneTexto({ type: 'doc', content: [{ type: 'bulletList', content: [{ type: 'listItem', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Mi texto' }] }] }] }] })).toBe(true)
  })
})

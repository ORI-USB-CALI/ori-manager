import type { DocumentoConvenio } from '../components/ConvenioEditor'
import type { SolicitudAntecedente } from './epica02'

type InformacionSolicitud = Pick<SolicitudAntecedente,
  'objeto' | 'justificacion' | 'actividades_por_parte' | 'metas_esperadas'>

/** Texto de partida opcional: sin variables, metadatos contractuales ni bloques obligatorios. */
export function informacionSolicitudComoDocumento(solicitud: InformacionSolicitud): DocumentoConvenio | null {
  const secciones: Array<[string, string | null]> = [
    ['Objeto propuesto', solicitud.objeto],
    ['Justificación', solicitud.justificacion],
    ['Actividades propuestas', solicitud.actividades_por_parte],
    ['Metas propuestas', solicitud.metas_esperadas],
  ]
  const content = secciones.flatMap(([titulo, valor]) => {
    if (!valor?.trim()) return []
    return [
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: titulo }] },
      ...valor.trim().split(/\r?\n/).map((linea) => ({
        type: 'paragraph',
        ...(linea.trim() ? { content: [{ type: 'text', text: linea.trim() }] } : {}),
      })),
    ]
  })
  return content.length ? { type: 'doc', content } : null
}

export function documentoTieneTexto(nodo: unknown): boolean {
  if (!nodo || typeof nodo !== 'object') return false
  if ('text' in nodo && typeof nodo.text === 'string' && nodo.text.trim()) return true
  return 'content' in nodo && Array.isArray(nodo.content) && nodo.content.some(documentoTieneTexto)
}

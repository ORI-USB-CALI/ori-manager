import { enumLabel } from './tableFormatters'
import { Select } from './Select'
import type { CatalogosConsulta } from '../pages/consultaConvenios'
import { ETIQUETA_TIPO, type EstadoConvenio, type TipoAliado } from '../pages/epica02'

interface FiltrosAvanzadosProps {
  catalogos: CatalogosConsulta | undefined
  estados: EstadoConvenio[]
  tiposContraparte: TipoAliado[]
  programaId: string
  onEstadosChange: (estados: EstadoConvenio[]) => void
  onTiposContraparteChange: (tipos: TipoAliado[]) => void
  onProgramaIdChange: (valor: string) => void
}

function alternar<T>(lista: T[], valor: T): T[] {
  return lista.includes(valor) ? lista.filter((item) => item !== valor) : [...lista, valor]
}

export function FiltrosAvanzados({
  catalogos,
  estados,
  tiposContraparte,
  programaId,
  onEstadosChange,
  onTiposContraparteChange,
  onProgramaIdChange,
}: FiltrosAvanzadosProps) {
  return (
    <>
      <div className="form-group filtro-checkboxes">
        <span className="form-label">Estado</span>
        <div className="filtro-checkboxes-opciones">
          {(catalogos?.estados ?? []).map((estado) => (
            <label key={estado}>
              <input
                type="checkbox"
                checked={estados.includes(estado)}
                onChange={() => onEstadosChange(alternar(estados, estado))}
              />
              {enumLabel(estado)}
            </label>
          ))}
        </div>
      </div>

      <div className="form-group filtro-checkboxes">
        <span className="form-label">Tipo de contraparte</span>
        <div className="filtro-checkboxes-opciones">
          {(catalogos?.tipos_contraparte ?? []).map((tipo) => (
            <label key={tipo}>
              <input
                type="checkbox"
                checked={tiposContraparte.includes(tipo)}
                onChange={() => onTiposContraparteChange(alternar(tiposContraparte, tipo))}
              />
              {ETIQUETA_TIPO[tipo]}
            </label>
          ))}
        </div>
        <p className="form-help">
          Incluye convenios en trámite cuya contraparte todavía no es aliado formal.
        </p>
      </div>

      <Select
        id="filtro-programa"
        label="Programa académico"
        value={programaId}
        opciones={[
          { value: '', label: 'Todos los convenios' },
          { value: 'PROGRAMA', label: 'Todos los convenios de alcance por programa' },
          { value: 'INSTITUCIONAL', label: 'Alcance institucional / sin programa' },
          ...(programaId === 'URL_INVALIDA'
            ? [{ value: programaId, label: 'Combinación de alcance y programa inválida' }]
            : programaId.startsWith('programa:') && !catalogos?.programas.some(
                (programa) => `programa:${programa.id}` === programaId,
              )
              ? [{ value: programaId, label: `Programa solicitado: ${programaId.slice(9) || '(vacío)'}` }]
              : []),
          ...(catalogos?.programas ?? []).map((programa) => ({
            value: `programa:${programa.id}`,
            label: programa.nombre,
          })),
        ]}
        onChange={(evento) => onProgramaIdChange(evento.target.value)}
      />
    </>
  )
}

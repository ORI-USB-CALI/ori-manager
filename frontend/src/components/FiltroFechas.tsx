import type { TipoFiltroFecha } from '../pages/consultaConvenios'

const AYUDA: Record<TipoFiltroFecha, string> = {
  FORMALIZACION: 'Convenios cuya última firma se registró en el periodo.',
  VIGENCIA: 'Convenios que estuvieron vigentes en algún momento del periodo.',
}

interface FiltroFechasProps {
  tipoFecha: TipoFiltroFecha
  fechaDesde: string
  fechaHasta: string
  invalido: boolean
  onTipoFechaChange: (tipo: TipoFiltroFecha) => void
  onFechaDesdeChange: (valor: string) => void
  onFechaHastaChange: (valor: string) => void
  onQuitarFechas: () => void
}

export function FiltroFechas({
  tipoFecha,
  fechaDesde,
  fechaHasta,
  invalido,
  onTipoFechaChange,
  onFechaDesdeChange,
  onFechaHastaChange,
  onQuitarFechas,
}: FiltroFechasProps) {
  const hayRango = Boolean(fechaDesde || fechaHasta)

  return (
    <div className="form-group filtro-fechas">
      <span className="form-label" id="filtro-fechas-criterio-label">
        Filtrar por
      </span>
      <div role="radiogroup" aria-labelledby="filtro-fechas-criterio-label" className="filtro-fechas-radios">
        <label>
          <input
            type="radio"
            name="tipo_fecha"
            value="FORMALIZACION"
            checked={tipoFecha === 'FORMALIZACION'}
            onChange={() => onTipoFechaChange('FORMALIZACION')}
          />
          Fecha de formalización
        </label>
        <label>
          <input
            type="radio"
            name="tipo_fecha"
            value="VIGENCIA"
            checked={tipoFecha === 'VIGENCIA'}
            onChange={() => onTipoFechaChange('VIGENCIA')}
          />
          Vigencia
        </label>
      </div>
      <p className="form-help">{AYUDA[tipoFecha]}</p>

      <div className="filtro-fechas-rango">
        <label className="form-group" htmlFor="filtro-fecha-desde">
          <span className="form-label">Desde</span>
          <input
            id="filtro-fecha-desde"
            type="date"
            className={`form-control ${invalido ? 'is-invalid' : ''}`}
            value={fechaDesde}
            aria-invalid={invalido || undefined}
            aria-describedby={invalido ? 'filtro-fechas-error' : undefined}
            onChange={(evento) => onFechaDesdeChange(evento.target.value)}
          />
        </label>
        <label className="form-group" htmlFor="filtro-fecha-hasta">
          <span className="form-label">Hasta</span>
          <input
            id="filtro-fecha-hasta"
            type="date"
            className={`form-control ${invalido ? 'is-invalid' : ''}`}
            value={fechaHasta}
            aria-invalid={invalido || undefined}
            aria-describedby={invalido ? 'filtro-fechas-error' : undefined}
            onChange={(evento) => onFechaHastaChange(evento.target.value)}
          />
        </label>
        {hayRango && (
          <button type="button" className="btn btn-outline btn-small" onClick={onQuitarFechas}>
            Quitar fechas
          </button>
        )}
      </div>
      {invalido && (
        <span id="filtro-fechas-error" className="form-error">
          El rango de fechas no es válido
        </span>
      )}
    </div>
  )
}

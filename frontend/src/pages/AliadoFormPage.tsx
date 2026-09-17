import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/http'
import { useAliado, useCrearAliado, useEditarAliado } from '../features/aliados/hooks'
import {
  TIPO_ALIADO_ETIQUETA,
  type AliadoCrear,
  type AliadoLeer,
  type TipoAliado,
} from '../features/aliados/types'

type Campos = Required<AliadoCrear>

const CAMPOS_VACIOS: Campos = {
  identificacion: '',
  nombre: '',
  tipo: 'universidad',
  sector_economico: '',
  ciudad: '',
  direccion: '',
  telefono: '',
  correo: '',
  sitio_web: '',
}

function desdeAliado(aliado: AliadoLeer): Campos {
  return {
    identificacion: aliado.identificacion,
    nombre: aliado.nombre,
    tipo: aliado.tipo,
    sector_economico: aliado.sector_economico ?? '',
    ciudad: aliado.ciudad ?? '',
    direccion: aliado.direccion ?? '',
    telefono: aliado.telefono ?? '',
    correo: aliado.correo ?? '',
    sitio_web: aliado.sitio_web ?? '',
  }
}

// Los opcionales vacíos viajan como null, igual que los espera el schema.
function aPayload(campos: Campos): AliadoCrear {
  const opcional = (v: string) => (v.trim() === '' ? null : v.trim())
  return {
    identificacion: campos.identificacion.trim(),
    nombre: campos.nombre.trim(),
    tipo: campos.tipo,
    sector_economico: opcional(campos.sector_economico ?? ''),
    ciudad: opcional(campos.ciudad ?? ''),
    direccion: opcional(campos.direccion ?? ''),
    telefono: opcional(campos.telefono ?? ''),
    correo: opcional(campos.correo ?? ''),
    sitio_web: opcional(campos.sitio_web ?? ''),
  }
}

// La página resuelve la carga; el formulario recibe su valor inicial ya listo.
export function AliadoFormPage() {
  const { aliadoId } = useParams<{ aliadoId: string }>()
  const idNumerico = aliadoId === undefined ? undefined : Number(aliadoId)
  const consulta = useAliado(idNumerico)

  if (idNumerico === undefined) {
    return <AliadoForm inicial={CAMPOS_VACIOS} />
  }

  if (consulta.isPending) {
    return (
      <div className="state-container">
        <h3 className="state-title">Cargando aliado...</h3>
      </div>
    )
  }

  if (consulta.isError) {
    return (
      <div className="state-container alert-notfound">
        <h3 className="state-title">No se pudo cargar el aliado</h3>
        <p className="state-description">{consulta.error.message}</p>
        <Link to="/aliados" className="btn btn-outline">
          Volver al listado
        </Link>
      </div>
    )
  }

  return <AliadoForm key={consulta.data.id} inicial={desdeAliado(consulta.data)} aliadoId={idNumerico} />
}

interface AliadoFormProps {
  inicial: Campos
  aliadoId?: number
}

function AliadoForm({ inicial, aliadoId }: AliadoFormProps) {
  const editando = aliadoId !== undefined
  const navigate = useNavigate()

  const crear = useCrearAliado()
  const editar = useEditarAliado(aliadoId ?? 0)
  const mutacion = editando ? editar : crear

  const [campos, setCampos] = useState<Campos>(inicial)

  const esEmpresa = campos.tipo === 'empresa'
  const error = mutacion.error instanceof ApiError ? mutacion.error : null
  const conflictoIdentificacion = error?.status === 409
  const faltaSector = error?.status === 422 && esEmpresa && !campos.sector_economico?.trim()

  function actualizar<K extends keyof Campos>(campo: K, valor: Campos[K]) {
    setCampos((c) => ({ ...c, [campo]: valor }))
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const payload = aPayload(campos)
    const guardado = editando
      ? await editar.mutateAsync(payload).catch(() => null)
      : await crear.mutateAsync(payload).catch(() => null)
    if (guardado) navigate(`/aliados/${guardado.id}`)
  }

  return (
    <>
      <nav className="caption">
        <Link to="/aliados">Aliados</Link> / {editando ? 'Editar aliado' : 'Nuevo aliado'}
      </nav>

      <div className="header-banner">
        <div>
          <h1>{editando ? 'Editar aliado' : 'Nuevo aliado'}</h1>
          <p>La identificación (NIT o documento) es el identificador institucional único.</p>
        </div>
      </div>

      <form className="card" onSubmit={enviar} noValidate>
        {conflictoIdentificacion && (
          <div className="state-container alert-forbidden" style={{ marginBottom: '16px' }}>
            <h3 className="state-title" style={{ color: 'var(--color-rojo)' }}>
              Esta identificación ya está registrada
            </h3>
            <p className="state-description">{error.message}</p>
            <Link
              to={`/aliados?buscar=${encodeURIComponent(campos.identificacion.trim())}`}
              className="btn btn-secondary"
            >
              Ver el aliado existente
            </Link>
          </div>
        )}

        {error && !conflictoIdentificacion && !faltaSector && (
          <div className="state-container alert-forbidden" style={{ marginBottom: '16px' }}>
            <h3 className="state-title">No se pudo guardar</h3>
            <p className="state-description">{error.message}</p>
          </div>
        )}

        <h2 style={{ marginBottom: '12px' }}>Identidad institucional</h2>

        <div className="form-group">
          <label htmlFor="identificacion" className="form-label">
            Identificación (NIT o documento) *
          </label>
          <input
            id="identificacion"
            className={`form-control${conflictoIdentificacion ? ' is-invalid' : ''}`}
            required
            disabled={editando}
            value={campos.identificacion}
            onChange={(e) => actualizar('identificacion', e.target.value)}
          />
          {editando && <small>No puede cambiarse después de creado.</small>}
        </div>

        <div className="form-group">
          <label htmlFor="nombre" className="form-label">
            Nombre de la entidad *
          </label>
          <input
            id="nombre"
            className="form-control"
            required
            value={campos.nombre}
            onChange={(e) => actualizar('nombre', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="tipo" className="form-label">
            Tipo de aliado *
          </label>
          <select
            id="tipo"
            className="form-control"
            value={campos.tipo}
            onChange={(e) => actualizar('tipo', e.target.value as TipoAliado)}
          >
            {Object.entries(TIPO_ALIADO_ETIQUETA).map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </div>

        {esEmpresa && (
          <div className="form-group">
            <label htmlFor="sector" className="form-label">
              Sector económico *
            </label>
            <input
              id="sector"
              className={`form-control${faltaSector ? ' is-invalid' : ''}`}
              value={campos.sector_economico ?? ''}
              onChange={(e) => actualizar('sector_economico', e.target.value)}
            />
            {faltaSector ? (
              <span className="form-error">{error.message}</span>
            ) : (
              <small>Obligatorio cuando el tipo es Empresa.</small>
            )}
          </div>
        )}

        <h2 style={{ margin: '8px 0 12px' }}>Ubicación y contacto</h2>

        <div className="form-group">
          <label htmlFor="ciudad" className="form-label">
            Ciudad
          </label>
          <input
            id="ciudad"
            className="form-control"
            value={campos.ciudad ?? ''}
            onChange={(e) => actualizar('ciudad', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="direccion" className="form-label">
            Dirección
          </label>
          <input
            id="direccion"
            className="form-control"
            value={campos.direccion ?? ''}
            onChange={(e) => actualizar('direccion', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="telefono" className="form-label">
            Teléfono
          </label>
          <input
            id="telefono"
            type="tel"
            className="form-control"
            value={campos.telefono ?? ''}
            onChange={(e) => actualizar('telefono', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="correo" className="form-label">
            Correo
          </label>
          <input
            id="correo"
            type="email"
            className="form-control"
            value={campos.correo ?? ''}
            onChange={(e) => actualizar('correo', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="sitio_web" className="form-label">
            Sitio web
          </label>
          <input
            id="sitio_web"
            type="url"
            className="form-control"
            value={campos.sitio_web ?? ''}
            onChange={(e) => actualizar('sitio_web', e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <Link to={editando ? `/aliados/${aliadoId}` : '/aliados'} className="btn btn-outline">
            Cancelar
          </Link>
          <button type="submit" className="btn btn-primary" disabled={mutacion.isPending}>
            {mutacion.isPending ? 'Guardando...' : 'Guardar aliado'}
          </button>
        </div>
      </form>
    </>
  )
}

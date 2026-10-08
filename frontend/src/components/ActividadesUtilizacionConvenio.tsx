import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'

import { ApiError } from '../app/api'
import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import {
  claveActividadesUtilizacion,
  ESTADOS_REGISTRO_UTILIZACION,
  registrarActividadUtilizacion,
  useActividadesUtilizacion,
  type ActividadUtilizacionCrear,
} from '../pages/actividadesUtilizacion'
import type { EstadoConvenio } from '../pages/epica02'

function fechaActividad(valor: string): string {
  return new Date(`${valor}T00:00:00Z`).toLocaleDateString('es-CO', { timeZone: 'UTC' })
}

export function ActividadesUtilizacionConvenio({ convenioId, estado }: { convenioId: number; estado: EstadoConvenio }) {
  const cliente = useQueryClient()
  const notify = useNotifications()
  const { puede } = useSesion()
  const actividades = useActividadesUtilizacion(convenioId)
  const puedeRegistrar = puede('convenios.editar') && ESTADOS_REGISTRO_UTILIZACION.includes(estado)

  const registrar = useMutation({
    mutationFn: (datos: ActividadUtilizacionCrear) => registrarActividadUtilizacion(convenioId, datos),
    onSuccess: async () => {
      notify({ type: 'success', message: 'Actividad de utilización registrada correctamente.' })
      await cliente.invalidateQueries({ queryKey: claveActividadesUtilizacion(convenioId) })
    },
    onError: (error) => notify({ type: 'error', message: error instanceof ApiError ? error.message : 'No fue posible registrar la actividad.' }),
  })

  function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const formulario = event.currentTarget
    const form = new FormData(formulario)
    registrar.mutate(
      {
        fecha: String(form.get('fecha') ?? ''),
        actividad: String(form.get('actividad') ?? '').trim(),
        descripcion: String(form.get('descripcion') ?? '').trim(),
        responsable: String(form.get('responsable') ?? '').trim(),
        observaciones: String(form.get('observaciones') ?? '').trim() || null,
      },
      { onSuccess: () => formulario.reset() },
    )
  }

  return (
    <section className="card">
      <h2>Actividades de utilización</h2>
      <p className="section-help">Actividades ya realizadas que evidencian el uso del convenio.</p>

      {actividades.isPending && <p className="estado-pagina">Cargando actividades…</p>}
      {actividades.isError && <p className="alert-error" role="alert">No se pudieron consultar las actividades de utilización.</p>}
      {actividades.data && actividades.data.length === 0 && <p className="section-help">No hay actividades de utilización registradas.</p>}
      {actividades.data && actividades.data.length > 0 && (
        <div className="table-container">
          <table className="table">
            <thead><tr><th>Fecha</th><th>Actividad</th><th>Descripción</th><th>Responsable</th><th>Observaciones</th></tr></thead>
            <tbody>
              {actividades.data.map((item) => (
                <tr key={item.id}>
                  <td>{fechaActividad(item.fecha)}</td>
                  <td>{item.actividad}</td>
                  <td>{item.descripcion}</td>
                  <td>{item.responsable}</td>
                  <td>{item.observaciones ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {puedeRegistrar && (
        <form onSubmit={enviar} className="form-grid">
          <h3 className="form-span-2">Registrar actividad</h3>
          <label className="form-group" htmlFor="utilizacion-fecha"><span className="form-label">Fecha *</span><input id="utilizacion-fecha" className="form-control" type="date" name="fecha" required /></label>
          <label className="form-group" htmlFor="utilizacion-responsable"><span className="form-label">Responsable *</span><input id="utilizacion-responsable" className="form-control" name="responsable" maxLength={200} required placeholder="Ej.: Facultad de Ingeniería" /></label>
          <label className="form-group form-span-2" htmlFor="utilizacion-actividad"><span className="form-label">Actividad *</span><input id="utilizacion-actividad" className="form-control" name="actividad" maxLength={200} required placeholder="Ej.: Movilidad académica de dos estudiantes de Ingeniería" /></label>
          <label className="form-group form-span-2" htmlFor="utilizacion-descripcion"><span className="form-label">Descripción *</span><textarea id="utilizacion-descripcion" className="form-control" name="descripcion" required /></label>
          <label className="form-group form-span-2" htmlFor="utilizacion-observaciones"><span className="form-label">Observaciones (opcional)</span><textarea id="utilizacion-observaciones" className="form-control" name="observaciones" /></label>
          <div className="page-toolbar form-span-2">
            <button className="btn btn-primary" type="submit" disabled={registrar.isPending}>{registrar.isPending ? 'Registrando…' : 'Registrar actividad'}</button>
          </div>
        </form>
      )}
    </section>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useNotifications } from '../app/notifications/useNotifications'
import { useSesion } from '../auth/sesion'
import { CLAVE_ALERTAS_VENCIMIENTO } from '../pages/alertasVencimiento'
import { type Convenio } from '../pages/epica02'
import { CLAVE_RENOVACIONES, iniciarRenovacion, mensajeErrorAccion } from '../pages/renovaciones'
import { ConfirmacionModal } from './ConfirmacionModal'

export function IniciarRenovacionFinalizado({ convenio }: { convenio: Convenio }) {
  const { puede } = useSesion()
  const autorizado = puede('convenios.gestionar_renovaciones')
  const cliente = useQueryClient()
  const notify = useNotifications()
  const navegar = useNavigate()
  const [confirmar, setConfirmar] = useState(false)
  const enviando = useRef(false)
  const mutacion = useMutation({
    mutationFn: () => iniciarRenovacion(convenio.id),
    onSuccess: async (datos) => {
      setConfirmar(false)
      notify({ type: 'success', message: 'La nueva elaboración de renovación se ha iniciado.' })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: CLAVE_RENOVACIONES }),
        cliente.invalidateQueries({ queryKey: CLAVE_ALERTAS_VENCIMIENTO }),
        cliente.invalidateQueries({ queryKey: ['convenios', 'tablero'] }),
        cliente.invalidateQueries({ queryKey: ['convenio', convenio.id] }),
      ])
      navegar(`/convenios/${datos.convenio_renovacion_id}`)
    },
    onError: async (error) => {
      setConfirmar(false)
      notify({ type: 'error', message: mensajeErrorAccion(error, 'iniciar') })
      await cliente.invalidateQueries({ queryKey: CLAVE_RENOVACIONES })
    },
    onSettled: () => { enviando.current = false },
    retry: false,
  })

  if (!autorizado || convenio.estado !== 'FINALIZADO') return null
  const habilitado = Boolean(convenio.fecha_vencimiento) && convenio.version_actual > 0

  function iniciar() {
    if (!autorizado || !habilitado || enviando.current || mutacion.isPending) return
    enviando.current = true
    mutacion.mutate()
  }

  return (
    <section className="card">
      <h2>Renovación del convenio</h2>
      <p className="section-help">Puedes iniciar una nueva elaboración a partir del documento de este convenio finalizado.</p>
      {!habilitado && <p className="section-help">Se requiere fecha de vencimiento y una versión documental válida.</p>}
      <div className="page-toolbar">
        <button type="button" className="btn btn-primary" disabled={!habilitado || mutacion.isPending} onClick={() => setConfirmar(true)}>Iniciar renovación</button>
      </div>
      {confirmar && (
        <ConfirmacionModal titulo="Iniciar renovación" confirmar="Iniciar renovación" procesando="Registrando…" pendiente={mutacion.isPending} onConfirmar={iniciar} onCerrar={() => setConfirmar(false)}>
          <h3>{convenio.codigo?.trim() || `Convenio #${convenio.id}`}</h3>
          <p>Se iniciará una nueva elaboración de convenio usando como base el documento vigente del convenio actual. ¿Deseas continuar?</p>
        </ConfirmacionModal>
      )}
    </section>
  )
}

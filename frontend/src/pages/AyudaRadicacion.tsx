import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { CLAVE_SESION, type Sesion, useSesion } from '../auth/sesion'
import { useRecorrido } from '../components/recorrido'
import { esSolicitante } from './onboardingInicial'
import { type EstadoFinalGuia, useEstadoGuia, useRegistrarEstadoGuia } from './estadoGuias'
import { DESTINOS_ACCIONES_SOLICITUD, PASOS_SECCIONES_SOLICITUD } from './guiaRadicacion'
import { crearPasosAccionesRadicacion } from './pasosAccionesRadicacion'

/** No recibe valores ni operaciones del formulario: únicamente explica su DOM. */
export function AyudaRadicacion({ devuelta }: { devuelta: boolean }) {
  const { sesion, puede } = useSesion()
  const cliente = useQueryClient()
  const recorrido = useRecorrido()
  const autorizado = Boolean(sesion && esSolicitante(sesion.rol.codigo) && puede('solicitudes.crear'))
  const [consultada, setConsultada] = useState(false)
  const [pendiente, setPendiente] = useState<EstadoFinalGuia | null>(null)
  const procesado = useRef(false)
  const vigente = useRef(true)
  const consulta = useEstadoGuia('GUIA_RADICACION', consultada && autorizado)
  const { registrar, isPending: guardando, isError: errorGuardado } = useRegistrarEstadoGuia('GUIA_RADICACION', 1)
  useEffect(() => {
    vigente.current = true
    return () => { vigente.current = false }
  }, [])
  const sigueEnSesion = useCallback(() => {
    const actual = cliente.getQueryData<Sesion | null>(CLAVE_SESION)
    return vigente.current && actual?.id === sesion?.id && actual?.rol.codigo === sesion?.rol.codigo
  }, [cliente, sesion])

  const sincronizar = useCallback((estado: EstadoFinalGuia) => {
    if (!sigueEnSesion()) return
    void registrar(estado).then(() => {
      if (sigueEnSesion()) setPendiente(null)
    }).catch(() => { /* Se conserva la intención y se informa el fallo con reintento explícito. */ })
  }, [registrar, sigueEnSesion])

  useEffect(() => {
    if (!pendiente || procesado.current || !consulta.isSuccess || consulta.isFetching) return
    procesado.current = true
    // Una respuesta desconocida nunca equivale a PENDIENTE. Se espera al GET.
    if (consulta.data.estado === 'COMPLETADO' || consulta.data.estado === pendiente) {
      void Promise.resolve().then(() => { if (sigueEnSesion()) setPendiente(null) })
      return
    }
    sincronizar(pendiente)
  }, [consulta.data?.estado, consulta.isFetching, consulta.isSuccess, pendiente, sigueEnSesion, sincronizar])

  if (!autorizado) return null

  function abrir() {
    if (!sigueEnSesion() || recorrido.activo || pendiente || guardando) return
    let terminado = false
    const finalizar = (estado: EstadoFinalGuia) => {
      if (terminado || !sigueEnSesion()) return
      terminado = true
      procesado.current = false
      setPendiente(estado)
    }
    if (recorrido.iniciar({
      guia: 'GUIA_RADICACION',
      pasos: [...PASOS_SECCIONES_SOLICITUD, ...crearPasosAccionesRadicacion(devuelta)],
      onComplete: () => finalizar('COMPLETADO'),
      onSkip: () => finalizar('OMITIDO'),
    })) {
      setConsultada(true)
      if (consulta.isError) void consulta.refetch()
    }
  }

  return (
    <div className="ayuda-radicacion">
      <button type="button" className="btn btn-outline" data-tour={DESTINOS_ACCIONES_SOLICITUD.ayuda}
        disabled={Boolean(recorrido.activo) || Boolean(pendiente) || guardando} onClick={abrir}>
        Ayuda: cómo diligenciar la solicitud
      </button>
      {consultada && consulta.isFetching && <p role="status">Consultando el estado de la guía. Puedes seguir utilizando el formulario.</p>}
      {consulta.isError && <>
        <p role="status">No se pudo consultar el estado de la guía. Su estado no se ha confirmado. Puedes seguir utilizando el formulario.</p>
        <button type="button" className="btn btn-outline btn-small" disabled={consulta.isFetching}
          onClick={() => { void consulta.refetch() }}>Reintentar consulta de la guía</button>
      </>}
      {errorGuardado && pendiente && <>
        <p role="status">No se pudo guardar el estado de la guía. Puedes seguir utilizando el formulario.</p>
        <button type="button" className="btn btn-outline btn-small" disabled={guardando}
          onClick={() => sincronizar(pendiente)}>Reintentar guardado de la guía</button>
      </>}
    </div>
  )
}

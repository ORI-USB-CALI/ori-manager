import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import './onboarding.css'

import type { Sesion } from '../auth/sesion'
import { CODIGO_ONBOARDING, esSolicitante, pasosOnboardingInicial, VERSION_ONBOARDING } from '../pages/onboardingInicial'
import { actualizarGuia, consultarGuia, type EstadoFinalGuia, type GuiaUsuario } from '../pages/estadoGuias'
import { useRecorrido } from './recorrido'

interface Props {
  sesion: Sesion
}

/** HU-38 FE-03: consulta, apertura automática y repetición manual del onboarding. */
export function OnboardingSolicitantes({ sesion }: Props) {
  const { pathname } = useLocation()
  const { activo, iniciar } = useRecorrido()
  const queryClient = useQueryClient()
  const habilitado = esSolicitante(sesion.rol.codigo)
  const queryKey = ['guias', sesion.id, CODIGO_ONBOARDING] as const
  // Impide que el efecto reabra la guía al cerrarla antes de persistir el estado.
  const autoIniciado = useRef<number | null>(null)
  const [errorGuardado, setErrorGuardado] = useState(false)

  const consulta = useQuery({
    queryKey,
    queryFn: () => consultarGuia(CODIGO_ONBOARDING),
    enabled: habilitado,
    retry: false,
  })

  const { mutate: guardarEstado, isPending: guardando } = useMutation({
    mutationFn: (estado: EstadoFinalGuia) => actualizarGuia(CODIGO_ONBOARDING, estado, VERSION_ONBOARDING),
    onSuccess: (respuesta: GuiaUsuario) => {
      queryClient.setQueryData(queryKey, respuesta)
      setErrorGuardado(false)
    },
    onError: () => {
      // El fallo nunca bloquea otras funciones. Ayuda permite volver a intentarlo.
      setErrorGuardado(true)
    },
  })

  const abrir = useCallback(() => {
    if (!habilitado || activo) return false
    const estadoInicial = consulta.data?.estado
    const iniciado = iniciar({
      guia: CODIGO_ONBOARDING,
      pasos: pasosOnboardingInicial(sesion),
      onComplete: () => {
        if (estadoInicial !== 'COMPLETADO') guardarEstado('COMPLETADO')
      },
      onSkip: () => {
        // Una reproducción manual no cambia el estado ya completado.
        if (estadoInicial !== 'COMPLETADO') guardarEstado('OMITIDO')
      },
    })
    if (iniciado) autoIniciado.current = sesion.id
    return iniciado
  }, [activo, consulta.data?.estado, guardarEstado, habilitado, iniciar, sesion])

  useEffect(() => {
    // La guía explica los accesos de Inicio: solo se inicia automáticamente allí.
    // En otras rutas, sigue disponible manualmente desde Ayuda.
    if (!habilitado || pathname !== '/' || !consulta.isSuccess || consulta.data?.estado !== 'PENDIENTE') return
    if (activo || autoIniciado.current === sesion.id) return
    abrir()
  }, [activo, abrir, consulta.data?.estado, consulta.isSuccess, habilitado, pathname, sesion.id])

  if (!habilitado) return null

  return (
    <div className="onboarding-ayuda">
      <button
        className="btn btn-outline"
        type="button"
        data-tour="ayuda-onboarding"
        disabled={Boolean(activo) || guardando}
        onClick={() => {
          setErrorGuardado(false)
          abrir()
        }}
      >
        Ayuda
      </button>
      {(consulta.isError || errorGuardado) && (
        <span role="status" className="onboarding-ayuda-error">
          No se pudo sincronizar la guía. Puedes seguir utilizando ORI Manager e intentar de nuevo desde Ayuda.
        </span>
      )}
    </div>
  )
}

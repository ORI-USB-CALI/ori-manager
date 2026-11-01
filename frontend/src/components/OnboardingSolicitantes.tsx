import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import './onboarding.css'

import { CLAVE_SESION, type Sesion } from '../auth/sesion'
import { CODIGO_ONBOARDING, esSolicitante, pasosOnboardingInicial, VERSION_ONBOARDING } from '../pages/onboardingInicial'
import { actualizarGuia, consultarGuia, type EstadoFinalGuia, type GuiaUsuario } from '../pages/estadoGuias'
import { useRecorrido } from './recorrido'
import { type EstadoVolver, esRutaInternaSegura, retornoSeguro } from './retornoVolver'

interface Props { sesion: Sesion }
interface Origen { to: string; estado?: EstadoVolver }

/** HU-38: Ayuda siempre reproduce el onboarding completo en Inicio. */
export function OnboardingSolicitantes({ sesion }: Props) {
  const ubicacion = useLocation()
  const navegar = useNavigate()
  const { activo, iniciar } = useRecorrido()
  const queryClient = useQueryClient()
  const habilitado = esSolicitante(sesion.rol.codigo)
  const queryKey = ['guias', sesion.id, CODIGO_ONBOARDING] as const
  const autoIniciado = useRef(false)
  const vigente = useRef(true)
  const guardadoEnCurso = useRef(false)
  const [manual, setManual] = useState(false)
  const [origen, setOrigen] = useState<Origen | null>(null)
  const [errorPreparacion, setErrorPreparacion] = useState(false)
  const [porSincronizar, setPorSincronizar] = useState<EstadoFinalGuia | null>(null)

  useEffect(() => {
    vigente.current = true
    return () => { vigente.current = false }
  }, [])

  const sigueEnSesion = useCallback(() => {
    const actual = queryClient.getQueryData<Sesion | null>(CLAVE_SESION)
    return vigente.current && actual?.id === sesion.id && actual.rol.codigo === sesion.rol.codigo
  }, [queryClient, sesion.id, sesion.rol.codigo])

  const consulta = useQuery({
    queryKey,
    queryFn: ({ signal }) => consultarGuia(CODIGO_ONBOARDING, signal),
    enabled: habilitado,
    retry: false,
    refetchOnWindowFocus: false,
  })

  const { mutate: guardarEstado, isPending: guardando, isError: errorGuardado } = useMutation({
    mutationFn: (estado: EstadoFinalGuia) => actualizarGuia(CODIGO_ONBOARDING, estado, VERSION_ONBOARDING),
    retry: false,
    onSuccess: (respuesta: GuiaUsuario) => {
      guardadoEnCurso.current = false
      if (!sigueEnSesion()) return
      queryClient.setQueryData<GuiaUsuario>(queryKey, (anterior) =>
        anterior?.estado === 'COMPLETADO' ? anterior : respuesta)
      setPorSincronizar(null)
    },
    onError: () => { guardadoEnCurso.current = false },
  })

  const registrar = useCallback((estado: EstadoFinalGuia) => {
    if (!sigueEnSesion() || guardadoEnCurso.current) return
    guardadoEnCurso.current = true
    setPorSincronizar(estado)
    guardarEstado(estado)
  }, [guardarEstado, sigueEnSesion])

  const abrir = useCallback(() => {
    if (!habilitado || activo || !consulta.isSuccess) return false
    const estadoInicial = consulta.data.estado
    let terminado = false
    const terminar = (estado: EstadoFinalGuia) => {
      if (terminado || !vigente.current) return
      terminado = true
      if (estadoInicial !== 'COMPLETADO') registrar(estado)
    }
    const iniciado = iniciar({
      guia: CODIGO_ONBOARDING,
      pasos: pasosOnboardingInicial(sesion),
      onComplete: () => terminar('COMPLETADO'),
      onSkip: () => terminar('OMITIDO'),
    })
    if (iniciado) autoIniciado.current = true
    return iniciado
  }, [activo, consulta.data, consulta.isSuccess, habilitado, iniciar, registrar, sesion])

  useEffect(() => {
    if (!habilitado || ubicacion.pathname !== '/' || !consulta.isSuccess || activo || porSincronizar) return
    if (!manual && (consulta.data.estado !== 'PENDIENTE' || autoIniciado.current)) return
    let terminado = false
    const intentar = () => {
      if (terminado || !document.querySelector('[data-tour="inicio-accesos-rapidos"]')) return false
      if (!abrir()) return false
      terminado = true
      setManual(false)
      return true
    }
    if (intentar()) return
    const observador = new MutationObserver(() => { intentar() })
    observador.observe(document.body, { childList: true, subtree: true })
    const limite = window.setTimeout(() => {
      if (terminado) return
      terminado = true
      autoIniciado.current = true
      setManual(false)
      setErrorPreparacion(true)
    }, 5000)
    return () => {
      terminado = true
      observador.disconnect()
      window.clearTimeout(limite)
    }
  }, [activo, abrir, consulta.data, consulta.isSuccess, habilitado, manual, porSincronizar, ubicacion.pathname])

  if (!habilitado) return null

  function solicitarRecorrido() {
    setErrorPreparacion(false)
    setManual(true)
    if (ubicacion.pathname !== '/') {
      const contexto = retornoSeguro(ubicacion.state)
      const to = `${ubicacion.pathname}${ubicacion.search}${ubicacion.hash}`
      setOrigen(esRutaInternaSegura(to) ? {
        to,
        estado: contexto ? { volver: contexto } : undefined,
      } : null)
      navegar('/')
    }
  }

  return (
    <div className="onboarding-ayuda">
      <button className="btn btn-outline" type="button" data-tour="ayuda-onboarding"
        title="Ver el onboarding inicial en Inicio"
        disabled={Boolean(activo) || manual || guardando || Boolean(porSincronizar) || !consulta.isSuccess}
        onClick={solicitarRecorrido}>
        Ayuda
      </button>
      {consulta.isError && (
        <>
          <span role="status" className="onboarding-ayuda-error">No se pudo consultar el estado de la guía. Puedes seguir utilizando ORI Manager.</span>
          <button className="btn btn-outline btn-small" disabled={consulta.isFetching} onClick={() => { void consulta.refetch() }}>Reintentar consulta</button>
        </>
      )}
      {errorGuardado && porSincronizar && (
        <>
          <span role="status" className="onboarding-ayuda-error">No se pudo guardar el estado de la guía. Puedes seguir utilizando ORI Manager y reintentar la sincronización.</span>
          <button className="btn btn-outline btn-small" disabled={guardando} onClick={() => registrar(porSincronizar)}>Reintentar guardado</button>
        </>
      )}
      {errorPreparacion && (
        <>
          <span role="status" className="onboarding-ayuda-error">No se pudo preparar el recorrido en Inicio. Puedes seguir utilizando la plataforma.</span>
          <button className="btn btn-outline btn-small" onClick={solicitarRecorrido}>Reintentar recorrido</button>
        </>
      )}
      {origen && !activo && !manual && ubicacion.pathname === '/' && (
        <Link className="btn btn-outline btn-small" to={origen.to} state={origen.estado} onClick={() => setOrigen(null)}>Volver a la pantalla anterior</Link>
      )}
    </div>
  )
}

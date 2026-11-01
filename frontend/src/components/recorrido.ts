// Motor de recorridos guiados (HU-38 FE-01). Es el único módulo que importa
// driver.js: si se cambia la librería, solo se toca este archivo.
import { driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import { createContext, useContext } from 'react'

import type { CodigoRol, Permiso, Sesion } from '../auth/sesion'

export type CodigoGuia = 'ONBOARDING_INICIAL' | 'GUIA_RADICACION'

export interface PasoRecorrido {
  /** Valor del atributo `data-tour` del elemento a resaltar. Sin destino, el paso se muestra centrado. */
  destino?: string
  /** Destinos equivalentes del DOM responsive, sin reproducir su lógica de menú. */
  destinosAlternativos?: string[]
  /** Conserva la explicación centrada si desaparece un destino esencial. */
  mantenerSinDestino?: boolean
  titulo: string
  descripcion: string
  /** Si se indica, el paso solo se muestra a quien tenga este permiso (HU-38 CA-05). */
  permiso?: Permiso
  /** Si se indica, el paso solo se muestra a estos roles (HU-39 CA-03). */
  roles?: CodigoRol[]
}

export interface OpcionesRecorrido {
  guia: CodigoGuia
  pasos: PasoRecorrido[]
  /** Se seleccionó Finalizar en el último paso. */
  onComplete?: () => void
  /** Se seleccionó Omitir, la X o Esc: los tres significan lo mismo (HU-38 CA-06, RN-04). */
  onSkip?: () => void
}

export interface ContextoRecorrido {
  /** Guía abierta en este momento, o `null` si no hay ninguna. */
  activo: CodigoGuia | null
  /** Abre el recorrido. Devuelve `false` si ya hay otro abierto (HU-39 RN-06) o no quedan pasos visibles. */
  iniciar: (opciones: OpcionesRecorrido) => boolean
}

export const RecorridoContext = createContext<ContextoRecorrido>({
  activo: null,
  iniciar: () => false,
})

export function useRecorrido() {
  return useContext(RecorridoContext)
}

const selector = (destino: string) => `[data-tour="${destino}"]`

function elementoVisible(destino: string) {
  // Descarta destinos ausentes u ocultos, por ejemplo dentro del menú móvil cerrado.
  const elemento = document.querySelector(selector(destino))
  if (!elemento || elemento.getClientRects().length === 0 || getComputedStyle(elemento).visibility === 'hidden') return undefined
  return elemento
}

export function pasosVisibles(
  pasos: PasoRecorrido[],
  sesion: Pick<Sesion, 'rol' | 'permisos'>,
): DriveStep[] {
  return pasos
    .filter((paso) =>
      (!paso.permiso || sesion.permisos.includes(paso.permiso))
      && (!paso.roles || paso.roles.includes(sesion.rol.codigo))
      && (!paso.destino || paso.mantenerSinDestino || elementoVisible(paso.destino)
        || paso.destinosAlternativos?.some((destino) => elementoVisible(destino))))
    .map((paso) => {
      const resolver = () => [paso.destino, ...(paso.destinosAlternativos ?? [])]
        .flatMap((destino) => destino ? [elementoVisible(destino)] : [])
        .find((elemento) => elemento !== undefined)
      return {
        // En 1.9 el runtime centra el paso si el resolver devuelve undefined;
        // su declaración TypeScript todavía exige Element en ese callback.
        element: paso.destino ? resolver as DriveStep['element'] : undefined,
        skipMissingElement: paso.mantenerSinDestino ? false : undefined,
        popover: { title: paso.titulo, description: paso.descripcion },
      }
    })
}

/**
 * Abre el recorrido y devuelve una función que lo cierra sin avisar a quien lo
 * abrió (para cuando se desmonta la aplicación, p. ej. al cerrar sesión).
 * Devuelve `null` si no queda ningún paso por mostrar.
 */
export function abrirRecorrido(
  opciones: OpcionesRecorrido,
  sesion: Pick<Sesion, 'rol' | 'permisos'>,
  alCerrar: () => void,
): (() => void) | null {
  const steps = pasosVisibles(opciones.pasos, sesion)
  if (steps.length === 0) return null

  let cerrado = false
  let silencioso = false
  // Todo cierre pasa por aquí: Finalizar (completo) o Omitir, la X y Esc (omisión).
  const terminar = (completo: boolean) => {
    if (cerrado) return
    cerrado = true
    window.removeEventListener('resize', adaptarDestino)
    instancia.destroy()
    alCerrar()
    if (silencioso) return
    if (completo) opciones.onComplete?.()
    else opciones.onSkip?.()
  }
  const instancia = driver({
    steps,
    animate: !(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false),
    showProgress: true,
    progressText: '{{current}} de {{total}}',
    nextBtnText: 'Siguiente',
    prevBtnText: 'Anterior',
    doneBtnText: 'Finalizar',
    closeBtnLabel: 'Omitir recorrido',
    // El recorrido solo informa: no se puede interactuar con lo resaltado y un
    // clic fuera del globo no lo cierra por accidente (HU-39 CA-07).
    disableActiveInteraction: true,
    overlayClickBehavior: 'none',
    // Si un destino desaparece durante el recorrido, se salta ese paso.
    skipMissingElement: true,
    onPopoverRender: (popover) => {
      const omitir = document.createElement('button')
      omitir.type = 'button'
      omitir.className = 'driver-popover-omitir-btn'
      omitir.textContent = 'Omitir'
      omitir.addEventListener('click', () => terminar(false))
      popover.footerButtons.prepend(omitir)
    },
    onDoneClick: () => terminar(true),
    // La X y Esc piden cerrar por aquí.
    onDestroyStarted: () => terminar(false),
  })
  // driver.js reposiciona sus tooltips. Solo resolvemos de nuevo el destino
  // equivalente si cambió el DOM responsive del paso actual.
  const adaptarDestino = () => {
    const paso = instancia.getActiveStep()
    if (typeof paso?.element !== 'function') return
    const destino = paso.element()
    const actual = instancia.getActiveElement()
    if (destino !== actual && !(destino === undefined && actual?.id === 'driver-dummy-element')) {
      instancia.moveTo(instancia.getActiveIndex() ?? 0)
    }
  }
  window.addEventListener('resize', adaptarDestino)
  instancia.drive()

  return () => {
    silencioso = true
    terminar(false)
  }
}

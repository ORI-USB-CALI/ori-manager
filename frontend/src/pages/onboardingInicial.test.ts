import { describe, expect, it } from 'vitest'

import type { Sesion } from '../auth/sesion'
import { CODIGO_ONBOARDING, esSolicitante, pasosOnboardingInicial, VERSION_ONBOARDING } from './onboardingInicial'

function sesion(rol: Sesion['rol']['codigo'], permisos: Sesion['permisos']): Pick<Sesion, 'rol' | 'permisos'> {
  return { rol: { codigo: rol, nombre: rol }, permisos }
}

describe('HU-38 FE-02: pasos de onboarding', () => {
  it('define el mismo código y versión que el contrato de backend', () => {
    expect(CODIGO_ONBOARDING).toBe('ONBOARDING_INICIAL')
    expect(VERSION_ONBOARDING).toBe(1)
  })

  it.each(['SOLICITANTE_INTERNO', 'SOLICITANTE_EXTERNO'] as const)(
    'contiene bienvenida, accesos y ayuda para %s', (rol) => {
      const pasos = pasosOnboardingInicial(sesion(rol, ['solicitudes.crear', 'solicitudes.ver_propias']))
      expect(pasos[0].titulo).toContain('Bienvenido')
      expect(pasos.map((p) => p.destino)).toContain('inicio-nueva-solicitud')
      expect(pasos.map((p) => p.destino)).toContain('inicio-mis-solicitudes')
      expect(pasos.map((p) => p.destino)).toContain('ayuda-onboarding')
      expect(pasos.at(-1)?.titulo).toBe('¡Todo listo!')
      expect(pasos.every((paso) => paso.roles?.includes(rol))).toBe(true)
    },
  )

  it('adapta los mensajes al tipo de solicitante', () => {
    const interno = pasosOnboardingInicial(sesion('SOLICITANTE_INTERNO', []))
    const externo = pasosOnboardingInicial(sesion('SOLICITANTE_EXTERNO', []))
    expect(interno[0].descripcion).not.toEqual(externo[0].descripcion)
  })

  it('no ofrece onboarding a los roles operativos ORI', () => {
    expect(esSolicitante('GESTOR_ORI')).toBe(false)
    expect(pasosOnboardingInicial(sesion('ADMINISTRADOR_ORI', ['solicitudes.crear']))).toEqual([])
  })

  it('marca los pasos sensibles con permisos y conserva pasos sin destino para móvil', () => {
    const pasos = pasosOnboardingInicial(sesion('SOLICITANTE_INTERNO', []))
    expect(pasos.find((paso) => paso.destino === 'inicio-nueva-solicitud')?.permiso).toBe('solicitudes.crear')
    expect(pasos.find((paso) => paso.destino === 'inicio-mis-solicitudes')?.permiso).toBe('solicitudes.ver_propias')
    expect(pasos.filter((paso) => !paso.destino)).toHaveLength(2)
  })
})

import type { Permiso } from '../auth/sesion'
import type { ElementoNav, EnlaceNav } from '../components/HeaderNav'

// Los permisos siguen decidiendo qué enlaces recibe el menú; los grupos vacíos
// se omiten para todos los roles.
export function crearNavegacion(puede: (permiso: Permiso) => boolean): ElementoNav[] {
  function grupo(label: string, opciones: [Permiso, EnlaceNav][]): ElementoNav[] {
    const enlaces = opciones.filter(([permiso]) => puede(permiso)).map(([, enlace]) => enlace)
    return enlaces.length ? [{ label, enlaces }] : []
  }

  return [
    { to: '/', label: 'Inicio', end: true },
    ...(puede('aliados.ver') ? [{ to: '/aliados', label: 'Aliados' }] : []),
    ...grupo('Solicitudes', [
      ['solicitudes.ver_recibidas', { to: '/ori/solicitudes', label: 'Solicitudes recibidas' }],
      ['solicitudes.ver_propias', { to: '/solicitudes', label: 'Mis solicitudes' }],
    ]),
    ...grupo('Convenios', [
      ['convenios.ver', { to: '/convenios', label: 'Consulta de convenios' }],
      ['convenios.ver', { to: '/convenios/tablero', label: 'Tablero de convenios' }],
      ['convenios.crear', { to: '/convenios/nuevo', label: 'Crear convenio manual' }],
      ['convenios.revisar', { to: '/revisiones-juridicas', label: 'Revisiones jurídicas' }],
    ]),
    ...(puede('convenios.gestionar_renovaciones') ? [{ to: '/renovaciones', label: 'Renovaciones' }] : []),
    ...(puede('convenios.ver_reportes') ? [
      { to: '/reportes/convenios-activos', label: 'Reportes' },
      { to: '/reportes/estadisticas-convenios', label: 'Estadísticas' },
    ] : []),
    ...grupo('Administración', [
      ['usuarios.ver', { to: '/admin/usuarios', label: 'Usuarios' }],
      ['auditoria.ver', { to: '/admin/bitacora', label: 'Bitácora' }],
    ]),
  ]
}

import { Link } from 'react-router-dom'

import { type Permiso, useSesion } from '../auth/sesion'

type IconoAcceso =
  | 'aliados'
  | 'convenios'
  | 'mis-solicitudes'
  | 'nueva-solicitud'
  | 'revisiones'
  | 'solicitudes-recibidas'
  | 'usuarios'

interface AccesoRapido {
  permiso: Permiso
  categoria: string
  titulo: string
  descripcion: string
  ruta: string
  cta: string
  icono: IconoAcceso
}

const ACCESOS_RAPIDOS: AccesoRapido[] = [
  {
    permiso: 'solicitudes.ver_recibidas',
    categoria: 'Gestión de solicitudes',
    titulo: 'Solicitudes recibidas',
    descripcion: 'Revisa las solicitudes radicadas y gestiona su aceptación, devolución o rechazo.',
    ruta: '/ori/solicitudes',
    cta: 'Ver solicitudes',
    icono: 'solicitudes-recibidas',
  },
  {
    permiso: 'convenios.ver',
    categoria: 'Gestión de convenios',
    titulo: 'Tablero de convenios',
    descripcion: 'Consulta la trazabilidad, etapa actual y avance de los convenios dentro del flujo ORI.',
    ruta: '/convenios/tablero',
    cta: 'Abrir tablero',
    icono: 'convenios',
  },
  {
    permiso: 'convenios.revisar',
    categoria: 'Gestión jurídica',
    titulo: 'Revisiones jurídicas',
    descripcion: 'Consulta las elaboraciones de convenio que requieren revisión y aval jurídico.',
    ruta: '/revisiones-juridicas',
    cta: 'Ver revisiones',
    icono: 'revisiones',
  },
  {
    permiso: 'aliados.ver',
    categoria: 'Directorio institucional',
    titulo: 'Aliados',
    descripcion: 'Consulta las instituciones, empresas y demás contrapartes registradas.',
    ruta: '/aliados',
    cta: 'Ver aliados',
    icono: 'aliados',
  },
  {
    permiso: 'usuarios.ver',
    categoria: 'Administración',
    titulo: 'Usuarios y roles',
    descripcion: 'Administra los usuarios internos, sus roles y estado de acceso al sistema.',
    ruta: '/admin/usuarios',
    cta: 'Gestionar usuarios',
    icono: 'usuarios',
  },
  {
    permiso: 'solicitudes.crear',
    categoria: 'Solicitudes',
    titulo: 'Nueva solicitud',
    descripcion: 'Inicia una nueva solicitud para la elaboración de un convenio.',
    ruta: '/solicitudes/nueva',
    cta: 'Crear solicitud',
    icono: 'nueva-solicitud',
  },
  {
    permiso: 'solicitudes.ver_propias',
    categoria: 'Solicitudes',
    titulo: 'Mis solicitudes',
    descripcion: 'Consulta tus solicitudes, su estado actual y las observaciones recibidas.',
    ruta: '/solicitudes',
    cta: 'Ver mis solicitudes',
    icono: 'mis-solicitudes',
  },
]

function IconoTarjeta({ tipo }: { tipo: IconoAcceso }) {
  const atributos = {
    'aria-hidden': true,
    className: 'acceso-rapido-icono-svg',
    fill: 'none',
    viewBox: '0 0 24 24',
    xmlns: 'http://www.w3.org/2000/svg',
  }

  switch (tipo) {
    case 'solicitudes-recibidas':
      return <svg {...atributos}><path d="M5 4h14v16H5zM8 8h8M8 12h5M8 16h4" /></svg>
    case 'convenios':
      return <svg {...atributos}><path d="M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v4H4zM14 15h6v4h-6z" /></svg>
    case 'revisiones':
      return <svg {...atributos}><path d="M6 3h9l3 3v15H6zM15 3v4h4M9 12l2 2 4-4M9 18h6" /></svg>
    case 'aliados':
      return <svg {...atributos}><path d="M4 20v-9h6v9M14 20V4h6v16M2 20h20M7 14h.01M17 8h.01M17 12h.01M17 16h.01" /></svg>
    case 'usuarios':
      return <svg {...atributos}><path d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM2 21v-2a6 6 0 0 1 12 0v2M17 8v6M14 11h6" /></svg>
    case 'nueva-solicitud':
      return <svg {...atributos}><path d="M5 3h10l4 4v14H5zM15 3v5h5M12 11v6M9 14h6" /></svg>
    case 'mis-solicitudes':
      return <svg {...atributos}><path d="M5 3h14v18H5zM9 3v3h6V3M8 11h8M8 15h8" /></svg>
  }
}

export function HomePage() {
  const { puede } = useSesion()
  const accesosDisponibles = ACCESOS_RAPIDOS.filter(({ permiso }) => puede(permiso))

  return (
    <>
      <section className="header-banner home-banner">
        <h1>Sistema de Gestión ORI</h1>
        <p>Oficina de Relaciones Internacionales — Universidad de San Buenaventura Cali</p>
      </section>

      <section className="accesos-rapidos" aria-labelledby="accesos-rapidos-titulo">
        <header className="accesos-rapidos-cabecera">
          <p className="accesos-rapidos-eyebrow">Portal de servicios</p>
          <h2 id="accesos-rapidos-titulo">Accesos rápidos</h2>
          <p>Selecciona una opción para continuar con tus actividades.</p>
        </header>

        <div className="accesos-rapidos-grid">
          {accesosDisponibles.map((acceso) => (
            <article className="acceso-rapido" key={acceso.permiso}>
              <Link className="acceso-rapido-enlace" to={acceso.ruta}>
                <div className="acceso-rapido-superior">
                  <span className="acceso-rapido-icono"><IconoTarjeta tipo={acceso.icono} /></span>
                  <span className="acceso-rapido-categoria">{acceso.categoria}</span>
                </div>
                <h3>{acceso.titulo}</h3>
                <p>{acceso.descripcion}</p>
                <span className="acceso-rapido-cta">
                  {acceso.cta}
                  <svg aria-hidden="true" fill="none" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                    <path d="m7 4 6 6-6 6" />
                  </svg>
                </span>
              </Link>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}

"""HU-33 tarea 7: permisos, lectura, resolución y duplicados a nivel de servicio."""

from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.models.notificacion import Notificacion
from backend.services.notificaciones import ServicioNotificaciones


def test_crear_no_duplica_mientras_este_pendiente(db, gestor):
    servicio = ServicioNotificaciones(db)

    primera = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        1,
        "Primer mensaje",
    )
    segunda = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        1,
        "Segundo mensaje, no debe crear fila nueva",
    )

    assert primera.id == segunda.id
    assert segunda.mensaje == "Primer mensaje"
    total = db.scalar(
        select(Notificacion)
        .where(
            Notificacion.usuario_id == gestor.id,
            Notificacion.tipo == TipoNotificacion.REVISION_JURIDICA_PENDIENTE.value,
            Notificacion.entidad_id == 1,
        )
    )
    assert total is not None
    filas = list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == gestor.id,
                Notificacion.tipo
                == TipoNotificacion.REVISION_JURIDICA_PENDIENTE.value,
                Notificacion.entidad_id == 1,
            )
        )
    )
    assert len(filas) == 1


def test_crear_permite_una_nueva_tras_resolver_la_anterior(db, gestor):
    servicio = ServicioNotificaciones(db)
    primera = servicio.crear(
        gestor.id,
        TipoNotificacion.SOLICITUD_DEVUELTA,
        EntidadNotificacion.SOLICITUD,
        5,
        "Primera devolución",
    )

    servicio.resolver(
        TipoNotificacion.SOLICITUD_DEVUELTA, EntidadNotificacion.SOLICITUD, 5
    )
    segunda = servicio.crear(
        gestor.id,
        TipoNotificacion.SOLICITUD_DEVUELTA,
        EntidadNotificacion.SOLICITUD,
        5,
        "Segunda devolución",
    )

    assert segunda.id != primera.id
    filas = list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == gestor.id,
                Notificacion.tipo == TipoNotificacion.SOLICITUD_DEVUELTA.value,
                Notificacion.entidad_id == 5,
            )
        )
    )
    assert len(filas) == 2
    assert sum(1 for f in filas if not f.resuelta) == 1


def test_crear_para_rol_excluye_usuarios_inactivos(db, revisor, crear_usuario):
    inactivo = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO, activo=False)

    creadas = ServicioNotificaciones(db).crear_para_rol(
        CodigoRol.REVISOR_ORI,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        7,
        "Convenio pendiente de revisión",
    )

    destinatarios = {n.usuario_id for n in creadas}
    assert revisor.id in destinatarios
    assert inactivo.id not in destinatarios


def test_crear_para_rol_no_notifica_a_otros_roles(db, revisor, gestor):
    creadas = ServicioNotificaciones(db).crear_para_rol(
        CodigoRol.REVISOR_ORI,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        8,
        "Convenio pendiente de revisión",
    )

    destinatarios = {n.usuario_id for n in creadas}
    assert gestor.id not in destinatarios


def test_marcar_leida_es_idempotente(db, gestor):
    servicio = ServicioNotificaciones(db)
    notificacion = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        9,
        "Mensaje",
    )

    primera = servicio.marcar_leida(notificacion.id, gestor)
    leida_en_primera = primera.leida_en
    segunda = servicio.marcar_leida(notificacion.id, gestor)

    assert segunda.leida is True
    assert segunda.leida_en == leida_en_primera


def test_resolver_sin_pendientes_no_hace_nada(db):
    # No debe lanzar ni fallar aunque no exista ninguna fila para esa entidad.
    ServicioNotificaciones(db).resolver(
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        999999,
    )


def test_resolver_no_afecta_una_entidad_distinta(db, gestor):
    servicio = ServicioNotificaciones(db)
    de_otro_convenio = servicio.crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        10,
        "Convenio 10",
    )

    servicio.resolver(
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        11,
    )

    db.refresh(de_otro_convenio)
    assert de_otro_convenio.resuelta is False

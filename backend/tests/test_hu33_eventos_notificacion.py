"""HU-33 CA-03 a CA-06: eventos del flujo que deben crear notificaciones."""

from uuid import uuid4

from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import EntidadNotificacion, EstadoSolicitud, TipoNotificacion
from backend.models.notificacion import Notificacion
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import ServicioConvenios
from backend.services.solicitudes import ServicioSolicitudes


def _notificaciones(db, usuario_id, tipo: TipoNotificacion) -> list[Notificacion]:
    return list(
        db.scalars(
            select(Notificacion).where(
                Notificacion.usuario_id == usuario_id,
                Notificacion.tipo == tipo.value,
            )
        )
    )


def _habilitar_contraparte(db, convenio, gestor, solicitante, revisor, crear_usuario):
    solicitud = db.get(SolicitudConvenio, convenio.solicitud_id)
    solicitud.solicitante_id = solicitante.id
    db.commit()
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ServicioConvenios(db).aprobar(
        convenio.id, primera.id, convenio.version_actual, revisor
    )
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio.id, segunda.id, convenio.version_actual, otro_revisor
    )
    db.refresh(convenio)
    return db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id,
            VersionConvenio.numero == convenio.version_actual,
        )
    )


def test_finalizar_elaboracion_notifica_a_todos_los_revisores_oris(
    db, gestor, revisor, crear_usuario, convenio_listo
):
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)

    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)

    for destinatario in (revisor, otro_revisor):
        notificaciones = _notificaciones(
            db, destinatario.id, TipoNotificacion.REVISION_JURIDICA_PENDIENTE
        )
        assert len(notificaciones) == 1
        assert notificaciones[0].entidad_tipo == EntidadNotificacion.CONVENIO.value
        assert notificaciones[0].entidad_id == convenio_listo.id
        assert notificaciones[0].resuelta is False


def test_devolver_revision_juridica_notifica_al_autor_del_convenio(
    db, gestor, revisor, convenio_listo
):
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    pendiente = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )

    ServicioConvenios(db).devolver(
        convenio_listo.id,
        pendiente.id,
        ["Falta anexar el certificado"],
        convenio_listo.version_actual,
        revisor,
    )

    notificaciones = _notificaciones(
        db, gestor.id, TipoNotificacion.DEVOLUCION_REVISION
    )
    assert len(notificaciones) == 1
    assert notificaciones[0].entidad_id == convenio_listo.id


def test_enviar_a_contraparte_notifica_al_solicitante(
    db, gestor, revisor, solicitante, crear_usuario, convenio_listo
):
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )

    ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, version.numero, gestor
    )

    notificaciones = _notificaciones(
        db, solicitante.id, TipoNotificacion.REVISION_CONTRAPARTE_PENDIENTE
    )
    assert len(notificaciones) == 1
    assert notificaciones[0].entidad_id == convenio_listo.id


def test_devolver_revision_contraparte_notifica_al_gestor_que_la_envio(
    db, gestor, revisor, solicitante, crear_usuario, convenio_listo
):
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, version.numero, gestor
    )

    ServicioConvenios(db).devolver_revision_contraparte(
        revision.id,
        version.numero,
        ["Ajustar antes de continuar"],
        solicitante,
    )

    notificaciones = _notificaciones(
        db, gestor.id, TipoNotificacion.DEVOLUCION_REVISION
    )
    assert len(notificaciones) == 1
    assert notificaciones[0].entidad_id == convenio_listo.id


def test_devolver_solicitud_notifica_al_solicitante(db, solicitante, gestor):
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex[:12]}",
        tipo_solicitante="INTERNO",
        solicitante_id=solicitante.id,
        objeto="Cooperación académica",
        nombre_aliado_propuesto="Universidad Contraparte",
        estado=EstadoSolicitud.RADICADA.value,
    )
    db.add(solicitud)
    db.commit()

    ServicioSolicitudes(db).devolver(
        solicitud.id, "Falta documentación de soporte", gestor
    )

    notificaciones = _notificaciones(
        db, solicitante.id, TipoNotificacion.SOLICITUD_DEVUELTA
    )
    assert len(notificaciones) == 1
    assert notificaciones[0].entidad_tipo == EntidadNotificacion.SOLICITUD.value
    assert notificaciones[0].entidad_id == solicitud.id

"""HU-33 CA-03 a CA-06: eventos del flujo que deben crear notificaciones."""

from copy import deepcopy
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.enums import EntidadNotificacion, EstadoSolicitud, TipoNotificacion
from backend.models.notificacion import Notificacion
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioElaboracionGuardar
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


# ---- Resolución de notificaciones (tarea 4) --------------------------------


def _no_resueltas(db, usuario_id, tipo: TipoNotificacion) -> list[Notificacion]:
    return [n for n in _notificaciones(db, usuario_id, tipo) if not n.resuelta]


def test_segunda_aprobacion_juridica_resuelve_pendiente_de_ambos_revisores(
    db, gestor, revisor, crear_usuario, convenio_listo
):
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ServicioConvenios(db).aprobar(
        convenio_listo.id, primera.id, convenio_listo.version_actual, revisor
    )
    # Tras la primera aprobación sigue pendiente la segunda instancia: no se resuelve aún.
    assert _no_resueltas(db, revisor.id, TipoNotificacion.REVISION_JURIDICA_PENDIENTE)
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )

    ServicioConvenios(db).aprobar(
        convenio_listo.id, segunda.id, convenio_listo.version_actual, otro_revisor
    )

    for destinatario in (revisor, otro_revisor):
        assert not _no_resueltas(
            db, destinatario.id, TipoNotificacion.REVISION_JURIDICA_PENDIENTE
        )


def test_devolver_revision_juridica_resuelve_pendiente_de_ambos_revisores(
    db, gestor, revisor, crear_usuario, convenio_listo
):
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
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

    for destinatario in (revisor, otro_revisor):
        assert not _no_resueltas(
            db, destinatario.id, TipoNotificacion.REVISION_JURIDICA_PENDIENTE
        )


def test_reenviar_a_juridica_resuelve_la_devolucion_anterior(
    db, gestor, revisor, convenio_listo
):
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    pendiente = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    devolucion = ServicioConvenios(db).devolver(
        convenio_listo.id,
        pendiente.id,
        ["Falta anexar el certificado"],
        convenio_listo.version_actual,
        revisor,
    )
    assert _no_resueltas(db, gestor.id, TipoNotificacion.DEVOLUCION_REVISION)
    for observacion in devolucion.observaciones:
        ServicioConvenios(db).atender_observacion(
            convenio_listo.id, observacion.id, "Certificado anexado", gestor
        )
    db.refresh(convenio_listo)
    actual = db.get(VersionConvenio, devolucion.version_convenio_id)
    contenido = deepcopy(actual.contenido)
    contenido["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Certificado anexado"}],
        }
    )
    ServicioConvenios(db).guardar_elaboracion(
        convenio_listo.id,
        ConvenioElaboracionGuardar(
            contenido=contenido, expected_version=convenio_listo.version_actual
        ),
        gestor,
    )
    db.refresh(convenio_listo)

    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)

    assert not _no_resueltas(db, gestor.id, TipoNotificacion.DEVOLUCION_REVISION)


def test_aprobar_revision_contraparte_resuelve_pendiente(
    db, gestor, revisor, solicitante, crear_usuario, convenio_listo
):
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, version.numero, gestor
    )

    ServicioConvenios(db).aprobar_revision_contraparte(
        revision.id, version.numero, solicitante
    )

    assert not _no_resueltas(
        db, solicitante.id, TipoNotificacion.REVISION_CONTRAPARTE_PENDIENTE
    )


def test_devolver_revision_contraparte_resuelve_pendiente(
    db, gestor, revisor, solicitante, crear_usuario, convenio_listo
):
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, version.numero, gestor
    )

    ServicioConvenios(db).devolver_revision_contraparte(
        revision.id, version.numero, ["Ajustar antes de continuar"], solicitante
    )

    assert not _no_resueltas(
        db, solicitante.id, TipoNotificacion.REVISION_CONTRAPARTE_PENDIENTE
    )


# ---- Resolución de SOLICITUD_DEVUELTA al volver a radicar ------------------


@pytest.fixture
def unidad_hu33(db):
    item = UnidadOrganizacional(
        codigo=f"U33-{uuid4().hex[:8]}",
        nombre="Facultad de prueba HU-33",
        tipo=TipoUnidad.FACULTAD.value,
    )
    db.add(item)
    db.commit()
    return item


def _payload_solicitud(tipo_convenio_id: int) -> dict[str, object]:
    return {
        "solicitante_unidad": "Dependencia de prueba",
        "solicitante_programa": "Programa de prueba",
        "solicitante_cargo": "Cargo presentado",
        "nombre_aliado_propuesto": "Entidad contraparte",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "tipo_aliado_propuesto": "EMPRESA",
        "correo_aliado_propuesto": "contacto@contraparte.com",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Avenida 1 # 2-3",
        "sector_economico_aliado_propuesto": "Educación",
        "contacto_contraparte_nombre": "Contacto contraparte",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": "persona@example.com",
        "tipo_convenio_id": tipo_convenio_id,
        "justificacion": "Justificación suficiente",
        "objeto": "Objeto del convenio",
        "actividades_por_parte": "Actividades definidas",
        "metas_esperadas": "Metas medibles",
        "implicacion_financiera": "Sin erogación inicial",
        "vigencia_estimada": "24 meses",
        "requisitos_renovacion": "Acuerdo escrito",
        "supervisor_usb_nombre": "Supervisora USB",
        "supervisor_usb_cargo": "Directora",
        "supervisor_usb_telefono": "6025550202",
        "supervisor_usb_correo": "supervisor.usb@example.com",
        "supervisor_contraparte_nombre": "Supervisor contraparte",
        "supervisor_contraparte_cargo": "Coordinador",
        "supervisor_contraparte_telefono": "3005550303",
        "supervisor_contraparte_correo": "supervisor.contraparte@example.com",
        "observaciones": "Sin observaciones",
    }


def _subir_documento_representacion(client, solicitud_id: int) -> None:
    respuesta = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "OTRO_DOCUMENTO_REPRESENTACION"},
        files={
            "archivo": (
                "representacion.pdf",
                BytesIO(b"%PDF-1.4 soporte"),
                "application/pdf",
            )
        },
    )
    assert respuesta.status_code == 201, respuesta.text


def test_radicar_de_nuevo_resuelve_la_notificacion_de_solicitud_devuelta(
    db, client, crear_usuario, entrar_como, unidad_hu33, gestor
):
    tipo_convenio = db.scalar(
        select(TipoConvenio).where(TipoConvenio.codigo == "MARCO")
    )
    assert tipo_convenio is not None
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO
    )
    solicitante.unidad_organizacional_id = unidad_hu33.id
    solicitante.cargo = "Coordinador"
    db.commit()
    entrar_como(solicitante)
    creado = client.post("/api/solicitudes", json=_payload_solicitud(tipo_convenio.id))
    assert creado.status_code == 201, creado.text
    solicitud_id = creado.json()["id"]
    _subir_documento_representacion(client, solicitud_id)
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    entrar_como(gestor)
    devuelta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Falta ajustar el objeto del convenio"},
    )
    assert devuelta.status_code == 200, devuelta.text
    assert _no_resueltas(db, solicitante.id, TipoNotificacion.SOLICITUD_DEVUELTA)

    entrar_como(solicitante)
    reenvio = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert reenvio.status_code == 200, reenvio.text

    assert not _no_resueltas(db, solicitante.id, TipoNotificacion.SOLICITUD_DEVUELTA)

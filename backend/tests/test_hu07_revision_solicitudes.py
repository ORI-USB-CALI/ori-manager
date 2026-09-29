from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio


def _datos_completos(tipo_convenio_id: int) -> dict[str, object]:
    return {
        "nombre_aliado_propuesto": "Universidad Contraparte",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": "convenios@contraparte.example",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Calle 1 # 2-3",
        "contacto_contraparte_nombre": "Ana Pérez",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": "ana@contraparte.example",
        "tipo_convenio_id": tipo_convenio_id,
        "justificacion": "Fortalecer la cooperación académica",
        "objeto": "Desarrollar cooperación académica",
        "actividades_por_parte": "Intercambios y proyectos conjuntos",
        "metas_esperadas": "Dos proyectos durante la vigencia",
        "implicacion_financiera": "Sin erogación inicial",
        "vigencia_estimada": "24 meses",
        "requisitos_renovacion": "Evaluación y acuerdo escrito",
        "supervisor_usb_nombre": "Carlos Ruiz",
        "supervisor_usb_cargo": "Coordinador",
        "supervisor_usb_telefono": "6025550202",
        "supervisor_usb_correo": "carlos@usb.example",
        "supervisor_contraparte_nombre": "María Salas",
        "supervisor_contraparte_cargo": "Coordinadora",
        "supervisor_contraparte_telefono": "3005550303",
        "supervisor_contraparte_correo": "maria@contraparte.example",
    }


@pytest.fixture
def crear_solicitud(db, solicitante):
    def _crear(estado: EstadoSolicitud = EstadoSolicitud.RADICADA) -> SolicitudConvenio:
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex[:12]}",
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            solicitante_id=solicitante.id,
            objeto="Cooperación académica",
            nombre_aliado_propuesto="Universidad Contraparte",
            estado=estado.value,
        )
        db.add(solicitud)
        db.commit()
        return solicitud

    return _crear


def test_solicitud_sin_decision_tiene_campos_nulos(crear_solicitud):
    solicitud = crear_solicitud(EstadoSolicitud.APROBADA)
    assert solicitud.decidida_por_id is None
    assert solicitud.fecha_decision is None


def test_ca01_gestor_consulta_detalle_de_solicitud_pendiente(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    respuesta = client.get(f"/api/solicitudes/recibidas/{solicitud.id}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "RADICADA"
    assert cuerpo["solicitante_id"] == solicitud.solicitante_id
    assert cuerpo["nombre_aliado_propuesto"] == "Universidad Contraparte"
    assert "documentos" in cuerpo


def test_ca02_aceptar_registra_responsable_fecha_y_auditoria(
    client, db, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "APROBADA"
    assert cuerpo["decidida_por_id"] == gestor.id
    assert cuerpo["decidida_por_nombre"] == gestor.nombre_completo
    assert cuerpo["fecha_decision"] is not None
    auditoria = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "solicitud",
            Auditoria.registro_id == solicitud.id,
            Auditoria.campo == "estado",
        )
    )
    assert (auditoria.valor_anterior, auditoria.valor_nuevo, auditoria.usuario_id) == (
        "RADICADA",
        "APROBADA",
        gestor.id,
    )


def test_ca03_aceptar_no_crea_convenio(client, db, gestor, crear_solicitud):
    solicitud = crear_solicitud()
    client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id))
        is None
    )
    detalle = client.get(f"/api/solicitudes/recibidas/{solicitud.id}").json()
    assert detalle["convenio_id"] is None


def test_ca04_rechazar_conserva_motivo_y_sigue_consultable(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud(EstadoSolicitud.EN_ESTUDIO)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar",
        json={"motivo": "  La contraparte no cumple requisitos  "},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RECHAZADA"
    assert respuesta.json()["motivo_rechazo"] == "La contraparte no cumple requisitos"
    bandeja = client.get("/api/solicitudes/recibidas").json()["items"]
    assert solicitud.id in {item["id"] for item in bandeja}


def test_devolver_registra_decision_observaciones_auditoria_y_no_crea_convenio(
    client, db, gestor, crear_solicitud
):
    solicitud = crear_solicitud(EstadoSolicitud.EN_ESTUDIO)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/devolver",
        json={"observaciones": "  Corregir la vigencia y los soportes  "},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "DEVUELTA"
    assert cuerpo["observaciones_devolucion"] == ("Corregir la vigencia y los soportes")
    assert cuerpo["decidida_por_id"] == gestor.id
    assert cuerpo["decidida_por_nombre"] == gestor.nombre_completo
    assert cuerpo["fecha_decision"] is not None
    auditorias = list(
        db.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "solicitud",
                Auditoria.registro_id == solicitud.id,
            )
        )
    )
    assert {
        (item.campo, item.valor_anterior, item.valor_nuevo, item.usuario_id)
        for item in auditorias
    } == {
        ("estado", "EN_ESTUDIO", "DEVUELTA", gestor.id),
        (
            "observaciones_devolucion",
            None,
            "Corregir la vigencia y los soportes",
            gestor.id,
        ),
    }
    assert (
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id)) is None
    )


@pytest.mark.parametrize(
    "payload", [{}, {"observaciones": ""}, {"observaciones": "   "}]
)
def test_devolver_requiere_observaciones(client, gestor, crear_solicitud, payload):
    solicitud = crear_solicitud()
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/devolver", json=payload
    )
    assert respuesta.status_code == 422


def test_devuelta_no_inicia_elaboracion_y_no_admite_segunda_decision(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    devuelta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/devolver",
        json={"observaciones": "Corregir soportes"},
    )
    assert devuelta.status_code == 200
    assert (
        client.post(
            f"/api/solicitudes/recibidas/{solicitud.id}/iniciar-elaboracion"
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar").status_code
        == 409
    )
    assert (
        client.post(
            f"/api/solicitudes/recibidas/{solicitud.id}/devolver",
            json={"observaciones": "Otra decisión"},
        ).status_code
        == 409
    )


def test_solicitante_corrige_documentos_y_vuelve_a_radicar_devuelta(
    client, db, crear_usuario, entrar_como
):
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    solicitante.documento_identidad = "CE-123"
    solicitante.entidad_externa = "Fundación Solicitante"
    db.commit()
    entrar_como(solicitante)
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    creada = client.post("/api/solicitudes", json=_datos_completos(tipo.id))
    assert creada.status_code == 201
    solicitud_id = creada.json()["id"]
    documento = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={"archivo": ("rut.pdf", BytesIO(b"%PDF-1.4 rut"), "application/pdf")},
    )
    assert documento.status_code == 201
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    gestor = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    entrar_como(gestor)
    devuelta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Ajustar objeto y reemplazar el RUT"},
    )
    assert devuelta.status_code == 200
    fecha_decision = devuelta.json()["fecha_decision"]

    entrar_como(solicitante)
    corregida = client.patch(
        f"/api/solicitudes/{solicitud_id}", json={"objeto": "Objeto corregido"}
    )
    assert corregida.status_code == 200
    assert corregida.json()["observaciones_devolucion"] == (
        "Ajustar objeto y reemplazar el RUT"
    )
    eliminado = client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{documento.json()['id']}"
    )
    assert eliminado.status_code == 204
    db.expire_all()
    reemplazo = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                "rut-corregido.pdf",
                BytesIO(b"%PDF-1.4 rut corregido"),
                "application/pdf",
            )
        },
    )
    assert reemplazo.status_code == 201
    reradicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert reradicada.status_code == 200, reradicada.text
    assert reradicada.json()["estado"] == "RADICADA"
    assert reradicada.json()["decidida_por_id"] is None
    assert reradicada.json()["fecha_decision"] is None
    assert reradicada.json()["observaciones_devolucion"] == (
        "Ajustar objeto y reemplazar el RUT"
    )
    assert reradicada.json()["fecha_radicacion"] > fecha_decision


def test_rechazada_no_es_editable_ni_radicable(
    client, solicitante, entrar_como, crear_solicitud
):
    solicitud = crear_solicitud(EstadoSolicitud.RECHAZADA)
    entrar_como(solicitante)
    assert (
        client.patch(
            f"/api/solicitudes/{solicitud.id}", json={"objeto": "Cambio prohibido"}
        ).status_code
        == 409
    )
    assert client.post(f"/api/solicitudes/{solicitud.id}/radicar").status_code == 409


@pytest.mark.parametrize("motivo", ["", "   "])
def test_rechazo_sin_motivo_es_422(client, gestor, crear_solicitud, motivo):
    solicitud = crear_solicitud()
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": motivo}
    )
    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    "estado",
    [EstadoSolicitud.APROBADA, EstadoSolicitud.RECHAZADA, EstadoSolicitud.DEVUELTA],
)
@pytest.mark.parametrize("accion", ["aceptar", "rechazar"])
def test_no_se_decide_fuera_de_revision(
    client, gestor, crear_solicitud, estado, accion
):
    solicitud = crear_solicitud(estado)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/{accion}", json={"motivo": "x"}
    )
    assert respuesta.status_code == 409


def test_segunda_decision_no_pisa_la_primera(client, gestor, crear_solicitud):
    solicitud = crear_solicitud()
    aceptada = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert aceptada.status_code == 200
    segunda = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": "tarde"}
    )
    assert segunda.status_code == 409


def test_borrador_no_es_visible_para_decidir(client, gestor, crear_solicitud):
    solicitud = crear_solicitud(EstadoSolicitud.BORRADOR)
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "rol,tipo",
    [
        (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solo_gestion_ori_puede_decidir(
    client, crear_usuario, entrar_como, crear_solicitud, rol, tipo
):
    solicitud = crear_solicitud()
    entrar_como(crear_usuario(rol, tipo))
    aceptar = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    rechazar = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar", json={"motivo": "x"}
    )
    devolver = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/devolver",
        json={"observaciones": "x"},
    )
    assert (aceptar.status_code, rechazar.status_code, devolver.status_code) == (
        403,
        403,
        403,
    )


def test_administrador_tambien_puede_aceptar(
    client, crear_usuario, entrar_como, crear_solicitud
):
    solicitud = crear_solicitud()
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO))
    respuesta = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "estado",
    [EstadoSolicitud.RADICADA, EstadoSolicitud.EN_ESTUDIO, EstadoSolicitud.RECHAZADA],
)
def test_no_se_inicia_elaboracion_sin_aceptacion(
    client, db, gestor, crear_solicitud, estado
):
    solicitud = crear_solicitud(estado)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/iniciar-elaboracion"
    )
    assert respuesta.status_code == 409
    db.expire_all()
    assert db.get(SolicitudConvenio, solicitud.id).estado == estado.value


def test_rechazada_no_permite_crear_convenio_directo(client, gestor, crear_solicitud):
    solicitud = crear_solicitud(EstadoSolicitud.RECHAZADA)
    respuesta = client.post(
        "/api/convenios", json={"solicitud_id": solicitud.id, "objeto": "x"}
    )
    assert respuesta.status_code == 409


def test_aceptada_luego_inicia_elaboracion(client, gestor, crear_solicitud):
    solicitud = crear_solicitud()
    client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/iniciar-elaboracion"
    )
    assert respuesta.status_code == 200

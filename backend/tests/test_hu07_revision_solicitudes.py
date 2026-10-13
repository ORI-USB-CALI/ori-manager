from datetime import datetime
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
        db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud.id)) is None
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
    por_campo = {
        item.campo: (item.valor_anterior, item.valor_nuevo, item.usuario_id)
        for item in auditorias
    }
    assert set(por_campo) == {
        "estado",
        "observaciones_devolucion",
        "decidida_por_id",
        "fecha_decision",
    }
    assert por_campo["estado"] == ("EN_ESTUDIO", "DEVUELTA", gestor.id)
    assert por_campo["observaciones_devolucion"] == (
        None,
        "Corregir la vigencia y los soportes",
        gestor.id,
    )
    assert por_campo["decidida_por_id"] == (None, str(gestor.id), gestor.id)
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
    consulta_devuelta = client.get(f"/api/solicitudes/{solicitud_id}")
    assert consulta_devuelta.status_code == 200
    assert consulta_devuelta.json()["solicitante_id"] == solicitante.id
    assert consulta_devuelta.json()["estado"] == "DEVUELTA"
    assert consulta_devuelta.json()["observaciones_devolucion"] == (
        "Ajustar objeto y reemplazar el RUT"
    )
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

    # Dos rondas de devolución y una aprobación deben conservar cada auditoría.
    for ronda in range(2):
        entrar_como(solicitante)
        propia = client.get(f"/api/solicitudes/{solicitud_id}")
        assert propia.status_code == 200
        entrar_como(gestor)
        ori = client.get(f"/api/solicitudes/recibidas/{solicitud_id}")
        assert ori.status_code == 200
        for datos in [propia.json(), ori.json()]:
            assert datos["id"] == solicitud_id
            assert datos["estado"] == "RADICADA"
            assert datos["observaciones_devolucion"] == (
                "Ajustar objeto y reemplazar el RUT"
                if ronda == 0
                else "Precisar las metas de la segunda ronda"
            )
            assert datos["fecha_decision"] is None
            assert datos["decidida_por_id"] is None
        if ronda == 0:
            segunda = client.post(
                f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
                json={"observaciones": "Precisar las metas de la segunda ronda"},
            )
            assert segunda.status_code == 200
            entrar_como(solicitante)
            assert (
                client.patch(
                    f"/api/solicitudes/{solicitud_id}",
                    json={"metas_esperadas": "Metas precisadas"},
                ).status_code
                == 200
            )
            assert (
                client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code
                == 200
            )

    aprobada = client.post(f"/api/solicitudes/recibidas/{solicitud_id}/aceptar")
    assert aprobada.status_code == 200
    entrar_como(solicitante)
    final = client.get(f"/api/solicitudes/{solicitud_id}")
    assert final.status_code == 200
    assert final.json()["estado"] == "APROBADA"
    assert final.json()["observaciones_devolucion"] == (
        "Precisar las metas de la segunda ronda"
    )
    db.expire_all()
    historial = list(
        db.scalars(
            select(Auditoria)
            .where(
                Auditoria.entidad == "solicitud", Auditoria.registro_id == solicitud_id
            )
            .order_by(Auditoria.id)
        )
    )
    estados = [a for a in historial if a.campo == "estado"]
    assert [(a.valor_anterior, a.valor_nuevo, a.usuario_id) for a in estados] == [
        ("BORRADOR", "RADICADA", solicitante.id),
        ("RADICADA", "DEVUELTA", gestor.id),
        ("DEVUELTA", "RADICADA", solicitante.id),
        ("RADICADA", "DEVUELTA", gestor.id),
        ("DEVUELTA", "RADICADA", solicitante.id),
        ("RADICADA", "APROBADA", gestor.id),
    ]
    assert all(a.fecha_hora.tzinfo is not None for a in historial)
    assert [a.fecha_hora for a in estados] == sorted(a.fecha_hora for a in estados)
    assert estados[1].fecha_hora == datetime.fromisoformat(fecha_decision)
    assert estados[-1].fecha_hora == datetime.fromisoformat(
        aprobada.json()["fecha_decision"]
    )
    motivos = [a for a in historial if a.campo == "observaciones_devolucion"]
    assert [(a.valor_anterior, a.valor_nuevo, a.usuario_id) for a in motivos] == [
        (None, "Ajustar objeto y reemplazar el RUT", gestor.id),
        (
            "Ajustar objeto y reemplazar el RUT",
            "Precisar las metas de la segunda ronda",
            gestor.id,
        ),
    ]
    assert [a.fecha_hora for a in motivos] == [
        estados[1].fecha_hora,
        estados[3].fecha_hora,
    ]


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


def test_ht01_rechazo_conserva_motivo_y_auditoria_para_solicitante(
    client, db, gestor, solicitante, entrar_como, crear_solicitud
):
    solicitud = crear_solicitud()
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud.id}/rechazar",
        json={"motivo": "Falta documentación legal"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RECHAZADA"
    assert respuesta.json()["motivo_rechazo"] == "Falta documentación legal"
    assert respuesta.json()["fecha_decision"] is not None
    cambios = list(
        db.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "solicitud", Auditoria.registro_id == solicitud.id
            )
        )
    )
    assert any(
        c.campo == "estado"
        and c.valor_nuevo == "RECHAZADA"
        and c.usuario_id == gestor.id
        for c in cambios
    )
    assert any(
        c.campo == "motivo_rechazo"
        and c.valor_nuevo == "Falta documentación legal"
        and c.usuario_id == gestor.id
        for c in cambios
    )
    entrar_como(solicitante)
    consultada = client.get(f"/api/solicitudes/{solicitud.id}")
    assert consultada.status_code == 200
    assert consultada.json()["id"] == solicitud.id
    assert consultada.json()["solicitante_id"] == solicitante.id
    assert consultada.json()["estado"] == "RECHAZADA"
    assert consultada.json()["motivo_rechazo"] == "Falta documentación legal"


def test_ht01_aprobacion_seguida_de_consulta_no_genera_404(
    client, gestor, crear_solicitud
):
    solicitud = crear_solicitud()
    aprobado = client.post(f"/api/solicitudes/recibidas/{solicitud.id}/aceptar")
    assert aprobado.status_code == 200
    assert aprobado.json()["estado"] == "APROBADA"
    assert aprobado.json()["fecha_decision"] is not None
    consultado = client.get(f"/api/solicitudes/recibidas/{solicitud.id}")
    assert consultado.status_code == 200
    assert consultado.json()["estado"] == "APROBADA"


@pytest.mark.parametrize("estado_inicial", ["RADICADA", "EN_ESTUDIO"])
@pytest.mark.parametrize(
    "decision, payload, estado_final, campo, motivo",
    [
        ("aceptar", None, "APROBADA", None, None),
        (
            "rechazar",
            {"motivo": "La contraparte no cumple los requisitos; revisar NIT 123."},
            "RECHAZADA",
            "motivo_rechazo",
            "La contraparte no cumple los requisitos; revisar NIT 123.",
        ),
        (
            "devolver",
            {"observaciones": "Precisar cláusula 3 y vigencia: 24 meses."},
            "DEVUELTA",
            "observaciones_devolucion",
            "Precisar cláusula 3 y vigencia: 24 meses.",
        ),
    ],
)
def test_ht01_decision_persistida_consistente_entre_portales_y_aislada(
    client,
    db,
    gestor,
    solicitante,
    entrar_como,
    crear_usuario,
    crear_solicitud,
    estado_inicial,
    decision,
    payload,
    estado_final,
    campo,
    motivo,
):
    solicitud = crear_solicitud(EstadoSolicitud(estado_inicial))
    solicitud_id = solicitud.id
    inicial = client.get(f"/api/solicitudes/recibidas/{solicitud_id}")
    assert inicial.status_code == 200
    assert inicial.json()["estado"] == estado_inicial
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/{decision}", json=payload
    )
    assert respuesta.status_code == 200, respuesta.text
    decision_ori = respuesta.json()
    fecha = datetime.fromisoformat(decision_ori["fecha_decision"])
    assert fecha.tzinfo is not None
    assert decision_ori["decidida_por_nombre"] == gestor.nombre_completo

    # Forzar una lectura de PostgreSQL, sin reutilizar objetos del identity map.
    db.expire_all()
    persistida = db.get(SolicitudConvenio, solicitud_id)
    assert persistida.estado == estado_final
    assert persistida.decidida_por_id == gestor.id
    assert persistida.fecha_decision == fecha
    auditorias = list(
        db.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "solicitud", Auditoria.registro_id == solicitud_id
            )
        )
    )
    assert {a.campo for a in auditorias} == {
        "estado",
        "decidida_por_id",
        "fecha_decision",
        *([campo] if campo else []),
    }
    auditoria_estado = next(a for a in auditorias if a.campo == "estado")
    assert (auditoria_estado.valor_anterior, auditoria_estado.valor_nuevo) == (
        estado_inicial,
        estado_final,
    )
    for auditoria in auditorias:
        assert auditoria.usuario_id == gestor.id
        assert auditoria.accion == "UPDATE"
        assert auditoria.fecha_hora == fecha
    if campo:
        auditoria_motivo = next(a for a in auditorias if a.campo == campo)
        assert auditoria_motivo.valor_anterior is None
        assert auditoria_motivo.valor_nuevo == motivo
        assert getattr(persistida, campo) == motivo

    ori = client.get(f"/api/solicitudes/recibidas/{solicitud_id}")
    assert ori.status_code == 200
    bandeja_ori = client.get("/api/solicitudes/recibidas")
    assert bandeja_ori.status_code == 200
    item_ori = next(i for i in bandeja_ori.json()["items"] if i["id"] == solicitud_id)
    entrar_como(solicitante)
    propia = client.get(f"/api/solicitudes/{solicitud_id}")
    assert propia.status_code == 200
    bandeja_propia = client.get("/api/solicitudes/mias")
    assert bandeja_propia.status_code == 200
    item_propio = next(
        i for i in bandeja_propia.json()["items"] if i["id"] == solicitud_id
    )
    for datos in [decision_ori, ori.json(), item_ori, propia.json(), item_propio]:
        assert datos["id"] == solicitud_id
        assert datos["consecutivo"] == solicitud.consecutivo
        assert datos["solicitante_id"] == solicitante.id
        assert datos["estado"] == estado_final
        assert datos["decidida_por_id"] == gestor.id
        assert datetime.fromisoformat(datos["fecha_decision"]) == fecha
        if campo:
            assert datos[campo] == motivo

    ajeno = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    entrar_como(ajeno)
    assert client.get(f"/api/solicitudes/{solicitud_id}").status_code == 404
    assert solicitud_id not in {
        i["id"] for i in client.get("/api/solicitudes/mias").json()["items"]
    }
    assert client.get(f"/api/solicitudes/recibidas/{solicitud_id}").status_code == 403

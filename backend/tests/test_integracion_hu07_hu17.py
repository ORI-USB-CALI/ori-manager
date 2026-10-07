from io import BytesIO

from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoRevisionConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio

URL_TABLERO = "/api/convenios/tablero"


def _datos_solicitud(tipo_convenio_id: int, sufijo: str) -> dict[str, object]:
    return {
        "nombre_aliado_propuesto": f"Universidad Integrada {sufijo}",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": f"900123{sufijo}",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": f"convenios-{sufijo}@contraparte.example",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Calle 1 # 2-3",
        "contacto_contraparte_nombre": "Ana Pérez",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": f"ana-{sufijo}@contraparte.example",
        "tipo_convenio_id": tipo_convenio_id,
        "justificacion": "Fortalecer la cooperación académica",
        "objeto": "Desarrollar cooperación académica internacional",
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
        "supervisor_contraparte_correo": f"maria-{sufijo}@contraparte.example",
    }


def _crear_y_radicar(client, tipo_convenio_id: int, sufijo: str) -> tuple[int, int]:
    creada = client.post(
        "/api/solicitudes", json=_datos_solicitud(tipo_convenio_id, sufijo)
    )
    assert creada.status_code == 201, creada.text
    solicitud_id = creada.json()["id"]
    documento = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                f"rut-{sufijo}.pdf",
                BytesIO(b"%PDF-1.4 soporte inicial"),
                "application/pdf",
            )
        },
    )
    assert documento.status_code == 201, documento.text
    radicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert radicada.status_code == 200, radicada.text
    assert radicada.json()["estado"] == "RADICADA"
    return solicitud_id, documento.json()["id"]


def _tarjetas(client) -> dict[int, dict]:
    respuesta = client.get(URL_TABLERO)
    assert respuesta.status_code == 200, respuesta.text
    return {item["id"]: item for item in respuesta.json()["convenios"]}


def test_flujo_integrado_devolucion_hasta_doble_revision_y_tablero(
    client, db, crear_usuario, entrar_como, crear_convenio
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO
    )
    solicitante.documento_identidad = "CE-HU07-HU17"
    solicitante.entidad_externa = "Fundación Integrada"
    gestor_a = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    gestor_b = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    administrador = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    revisor_a = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    revisor_b = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    db.commit()

    entrar_como(solicitante)
    solicitud_id, documento_id = _crear_y_radicar(client, tipo.id, "A")

    entrar_como(gestor_a)
    tablero_antes = set(_tarjetas(client))
    recibida = client.get(f"/api/solicitudes/recibidas/{solicitud_id}")
    assert recibida.status_code == 200
    devuelta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Corregir objeto y reemplazar el RUT"},
    )
    assert devuelta.status_code == 200, devuelta.text
    assert devuelta.json()["estado"] == "DEVUELTA"
    assert devuelta.json()["observaciones_devolucion"] == (
        "Corregir objeto y reemplazar el RUT"
    )
    assert db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud_id)) is None
    assert set(_tarjetas(client)) == tablero_antes
    auditoria_devolucion = list(
        db.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "solicitud",
                Auditoria.registro_id == solicitud_id,
                Auditoria.campo.in_(["estado", "observaciones_devolucion"]),
            )
        )
    )
    ids_auditoria = {item.id for item in auditoria_devolucion}
    assert {item.campo for item in auditoria_devolucion} == {
        "estado",
        "observaciones_devolucion",
    }

    entrar_como(solicitante)
    detalle = client.get(f"/api/solicitudes/{solicitud_id}")
    assert detalle.status_code == 200
    assert detalle.json()["observaciones_devolucion"] == (
        "Corregir objeto y reemplazar el RUT"
    )
    corregida = client.patch(
        f"/api/solicitudes/{solicitud_id}",
        json={"objeto": "Objeto corregido para integración HU-17"},
    )
    assert corregida.status_code == 200
    assert client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{documento_id}"
    ).status_code == 204
    db.expire_all()
    reemplazo = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                "rut-corregido.pdf",
                BytesIO(b"%PDF-1.4 soporte corregido"),
                "application/pdf",
            )
        },
    )
    assert reemplazo.status_code == 201
    reradicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert reradicada.status_code == 200, reradicada.text
    assert reradicada.json()["estado"] == "RADICADA"
    assert reradicada.json()["observaciones_devolucion"] == (
        "Corregir objeto y reemplazar el RUT"
    )
    assert ids_auditoria <= {
        item.id
        for item in db.scalars(
            select(Auditoria).where(
                Auditoria.entidad == "solicitud",
                Auditoria.registro_id == solicitud_id,
            )
        )
    }

    entrar_como(gestor_a)
    aceptada = client.post(f"/api/solicitudes/recibidas/{solicitud_id}/aceptar")
    assert aceptada.status_code == 200
    assert aceptada.json()["estado"] == "APROBADA"
    assert db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud_id)) is None
    assert set(_tarjetas(client)) == tablero_antes

    iniciada = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    )
    assert iniciada.status_code == 200, iniciada.text
    convenio_id = iniciada.json()["id"]
    assert iniciada.json()["estado"] == "EN_TRAMITE"
    convenio_a = db.get(Convenio, convenio_id)
    assert convenio_a.etapa_actual.codigo == "ELABORACION"
    convenio_b = crear_convenio(gestor_b)

    entrar_como(gestor_a)
    tarjeta_a = _tarjetas(client)[convenio_id]
    assert tarjeta_a["etapa_actual"]["codigo"] == "ELABORACION"
    assert tarjeta_a["responsable"]["id"] == gestor_a.id
    assert convenio_b.id in _tarjetas(client)
    entrar_como(gestor_b)
    tarjetas_b = _tarjetas(client)
    assert {convenio_id, convenio_b.id} <= set(tarjetas_b)
    entrar_como(administrador)
    tarjetas_admin = _tarjetas(client)
    assert {convenio_id, convenio_b.id} <= set(tarjetas_admin)
    entrar_como(revisor_a)
    tarjetas_revisor = _tarjetas(client)
    assert tarjetas_revisor[convenio_id]["puede_ver_detalle"] is False
    assert tarjetas_revisor[convenio_b.id]["puede_ver_detalle"] is False
    entrar_como(solicitante)
    assert client.get(URL_TABLERO).status_code == 403

    entrar_como(gestor_a)
    finalizada = client.post(
        f"/api/convenios/{convenio_id}/elaboracion/finalizar",
        json={
            "tipo_convenio_id": tipo.id,
            "objeto": "Objeto integrado listo para Jurídica",
            "alcance": "INSTITUCIONAL",
            "implicacion_financiera": "Sin erogación presupuestal",
            "duracion_meses": 24,
        },
    )
    assert finalizada.status_code == 200, finalizada.text
    assert db.get(Convenio, convenio_id).etapa_actual.codigo == (
        "REVISION_AVAL_JURIDICO"
    )
    tarjeta_gestor = _tarjetas(client)[convenio_id]
    assert tarjeta_gestor["etapa_actual"]["codigo"] == "REVISION_AVAL_JURIDICO"
    assert tarjeta_gestor["responsable"] is None
    assert tarjeta_gestor["etapa_actual"]["area_responsable"] == "Oficina Jurídica"
    entrar_como(administrador)
    assert _tarjetas(client)[convenio_id]["etapa_actual"]["codigo"] == (
        "REVISION_AVAL_JURIDICO"
    )
    entrar_como(revisor_a)
    assert _tarjetas(client)[convenio_id]["puede_ver_detalle"] is True

    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    aprobada_1 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{primera.id}/aprobar",
        json={"expected_version": convenio_a.version_actual},
    )
    assert aprobada_1.status_code == 200, aprobada_1.text
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
        )
    )
    assert segunda.instancia_juridica == 2
    assert _tarjetas(client)[convenio_id]["puede_ver_detalle"] is False
    assert convenio_id not in {
        item["convenio_id"]
        for item in client.get("/api/convenios/revisiones-juridicas/pendientes").json()
    }
    assert client.get(f"/api/convenios/{convenio_id}").status_code == 404
    assert client.get(f"/api/convenios/{convenio_id}/revision").status_code == 404

    entrar_como(revisor_b)
    assert _tarjetas(client)[convenio_id]["puede_ver_detalle"] is True
    assert convenio_id in {
        item["convenio_id"]
        for item in client.get("/api/convenios/revisiones-juridicas/pendientes").json()
    }
    assert client.get(f"/api/convenios/{convenio_id}").status_code == 200
    assert client.get(f"/api/convenios/{convenio_id}/revision").status_code == 200
    aprobada_2 = client.post(
        f"/api/convenios/{convenio_id}/revisiones/{segunda.id}/aprobar",
        json={"expected_version": convenio_a.version_actual},
    )
    assert aprobada_2.status_code == 200, aprobada_2.text

    entrar_como(administrador)
    contraparte = _tarjetas(client)[convenio_id]
    assert contraparte["etapa_actual"]["codigo"] == "REVISION_CONTRAPARTE"
    assert contraparte["etapa_actual"]["area_responsable"] == "Contraparte"
    assert contraparte["responsable"] is None


def test_flujo_integrado_rechazo_no_genera_convenio_ni_tarjeta(
    client, db, crear_usuario, entrar_como
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO
    )
    solicitante.documento_identidad = "CE-RECHAZO"
    solicitante.entidad_externa = "Fundación Rechazada"
    gestor = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    db.commit()

    entrar_como(solicitante)
    solicitud_id, _ = _crear_y_radicar(client, tipo.id, "B")
    entrar_como(gestor)
    tablero_antes = set(_tarjetas(client))
    rechazada = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/rechazar",
        json={"motivo": "La solicitud no cumple los requisitos"},
    )

    assert rechazada.status_code == 200
    assert rechazada.json()["estado"] == "RECHAZADA"
    assert db.scalar(select(Convenio).where(Convenio.solicitud_id == solicitud_id)) is None
    assert client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    ).status_code == 409
    assert set(_tarjetas(client)) == tablero_antes

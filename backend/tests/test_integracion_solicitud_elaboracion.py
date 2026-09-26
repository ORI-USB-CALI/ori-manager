from io import BytesIO

from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import AccionAuditoria, EstadoConvenio, EstadoSolicitud
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio


def _datos_solicitud(tipo_convenio_id: int) -> dict[str, object]:
    return {
        "nombre_aliado_propuesto": "Universidad del Pacífico",
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "tipo_aliado_propuesto": "UNIVERSIDAD",
        "correo_aliado_propuesto": "convenios@pacifico.example",
        "pais_aliado_propuesto": "Colombia",
        "ciudad_aliado_propuesto": "Cali",
        "telefono_aliado_propuesto": "6025550101",
        "direccion_aliado_propuesto": "Calle 1 # 2-3",
        "contacto_contraparte_nombre": "Ana Pérez",
        "contacto_contraparte_cargo": "Directora",
        "contacto_contraparte_telefono": "3001234567",
        "contacto_contraparte_correo": "ana@pacifico.example",
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
        "supervisor_contraparte_correo": "maria@pacifico.example",
        "observaciones": "Antecedente original inmutable",
    }


def test_flujo_real_solicitud_hasta_elaboracion(
    client, db, crear_usuario, entrar_como
) -> None:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO
    )
    solicitante.documento_identidad = "11223344"
    solicitante.entidad_externa = "Fundación Solicitante"
    db.commit()
    entrar_como(solicitante)

    creada = client.post(
        "/api/solicitudes", json=_datos_solicitud(tipo.id)
    )
    assert creada.status_code == 201
    solicitud_id = creada.json()["id"]
    documento = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={"archivo": ("rut.pdf", BytesIO(b"%PDF-1.4 soporte"), "application/pdf")},
    )
    assert documento.status_code == 201
    documento_id = documento.json()["id"]
    radicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert radicada.status_code == 200
    assert radicada.json()["estado"] == EstadoSolicitud.RADICADA
    original = {
        "tipo_convenio_id": radicada.json()["tipo_convenio_id"],
        "objeto": radicada.json()["objeto"],
        "implicacion_financiera": radicada.json()["implicacion_financiera"],
        "observaciones": radicada.json()["observaciones"],
    }
    borrador_oculto = client.post("/api/solicitudes", json={}).json()["id"]
    otra = client.post(
        "/api/solicitudes", json=_datos_solicitud(tipo.id)
    ).json()["id"]
    otro_documento = client.post(
        f"/api/solicitudes/{otra}/documentos",
        data={"tipo_documento": "RUT"},
        files={
            "archivo": (
                "otro-rut.pdf",
                BytesIO(b"%PDF-1.4 otro soporte"),
                "application/pdf",
            )
        },
    ).json()["id"]
    assert client.post(f"/api/solicitudes/{otra}/radicar").status_code == 200
    assert client.get("/api/solicitudes/recibidas").status_code == 403

    gestor = crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)
    entrar_como(gestor)
    assert client.get("/api/solicitudes/mias").status_code == 403
    bandeja = client.get("/api/solicitudes/recibidas")
    assert bandeja.status_code == 200
    recibido = next(
        item for item in bandeja.json()["items"] if item["id"] == solicitud_id
    )
    ids_recibidos = {item["id"] for item in bandeja.json()["items"]}
    assert borrador_oculto not in ids_recibidos
    assert otra in ids_recibidos
    assert recibido["convenio_id"] is None
    assert recibido["convenio_estado"] is None
    assert recibido["convenio_etapa"] is None
    assert recibido["tipo_convenio_nombre"] == tipo.nombre
    assert client.post(
        f"/api/solicitudes/recibidas/{borrador_oculto}/iniciar-elaboracion"
    ).status_code == 409
    assert client.get(f"/api/solicitudes/recibidas/{solicitud_id}").status_code == 200
    contenido = client.get(
        f"/api/solicitudes/recibidas/{solicitud_id}/documentos/{documento_id}/contenido"
    )
    assert contenido.status_code == 200
    assert contenido.content == b"%PDF-1.4 soporte"
    assert client.get(
        f"/api/solicitudes/recibidas/{solicitud_id}/documentos/"
        f"{otro_documento}/contenido"
    ).status_code == 404
    assert "ruta_almacenamiento" not in recibido

    crear_antes_de_iniciar = client.post(
        "/api/convenios",
        json={"solicitud_id": solicitud_id, "objeto": "No permitido"},
    )
    assert crear_antes_de_iniciar.status_code == 409

    revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(revisor)
    assert client.get("/api/solicitudes/recibidas").status_code == 403
    assert client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    ).status_code == 403

    administrador = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    solicitud_heredada = db.get(SolicitudConvenio, otra)
    solicitud_heredada.estado = EstadoSolicitud.EN_ESTUDIO.value
    db.commit()
    entrar_como(administrador)
    assert client.get("/api/solicitudes/mias").status_code == 403
    assert client.post("/api/solicitudes", json={}).status_code == 403
    assert client.post(
        f"/api/solicitudes/recibidas/{otra}/iniciar-elaboracion"
    ).status_code == 409
    assert client.post(
        f"/api/solicitudes/recibidas/{otra}/aceptar"
    ).status_code == 200
    iniciada_admin = client.post(
        f"/api/solicitudes/recibidas/{otra}/iniciar-elaboracion"
    )
    assert iniciada_admin.status_code == 200
    assert db.get(SolicitudConvenio, otra).estado == EstadoSolicitud.APROBADA

    entrar_como(solicitante)
    assert client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    ).status_code == 403

    entrar_como(gestor)
    assert client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/aceptar"
    ).status_code == 200
    iniciada = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    )
    assert iniciada.status_code == 200
    convenio_id = iniciada.json()["id"]
    convenio = db.get(Convenio, convenio_id)
    elaboracion = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    assert convenio.estado == EstadoConvenio.EN_TRAMITE
    assert convenio.etapa_actual_id == elaboracion.id
    bandeja_actualizada = client.get("/api/solicitudes/recibidas")
    assert bandeja_actualizada.status_code == 200
    recibida_actualizada = next(
        item
        for item in bandeja_actualizada.json()["items"]
        if item["id"] == solicitud_id
    )
    assert recibida_actualizada["estado"] == EstadoSolicitud.APROBADA
    assert recibida_actualizada["convenio_id"] == convenio.id
    assert recibida_actualizada["convenio_estado"] == EstadoConvenio.EN_TRAMITE
    assert recibida_actualizada["convenio_etapa"]["codigo"] == "ELABORACION"
    assert convenio.tipo_convenio_id == original["tipo_convenio_id"]
    assert convenio.objeto == original["objeto"]
    assert convenio.implicacion_financiera == original["implicacion_financiera"]
    assert convenio.alcance is None
    assert convenio.unidad_organizacional_id is None
    assert convenio.fecha_inicio is None
    assert convenio.fecha_vencimiento is None
    assert convenio.duracion_meses is None

    segundo_intento = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/iniciar-elaboracion"
    )
    assert segundo_intento.status_code == 200
    assert segundo_intento.json()["id"] == convenio_id
    assert db.scalar(
        select(func.count()).select_from(Convenio).where(
            Convenio.solicitud_id == solicitud_id
        )
    ) == 1

    aprobada_sin_convenio = db.get(SolicitudConvenio, borrador_oculto)
    aprobada_sin_convenio.estado = EstadoSolicitud.APROBADA.value
    aprobada_sin_convenio.objeto = "Solicitud aprobada heredada"
    db.commit()
    recuperada = client.post(
        f"/api/solicitudes/recibidas/{borrador_oculto}/iniciar-elaboracion"
    )
    assert recuperada.status_code == 200
    assert recuperada.json()["solicitud_id"] == borrador_oculto

    solicitud = db.get(SolicitudConvenio, solicitud_id)
    assert solicitud.estado == EstadoSolicitud.APROBADA
    assert solicitud.objeto == original["objeto"]
    assert solicitud.implicacion_financiera == original["implicacion_financiera"]
    assert solicitud.observaciones == original["observaciones"]
    doc = db.get(Documento, documento_id)
    assert doc.solicitud_id == solicitud_id
    assert doc.convenio_id is None
    historial = db.scalars(
        select(HistorialEtapa).where(HistorialEtapa.convenio_id == convenio_id)
    ).all()
    assert len(historial) == 1
    assert historial[0].etapa_origen_id is None
    assert historial[0].responsable_id == gestor.id

    auditorias = db.scalars(
        select(Auditoria)
        .where(
            Auditoria.entidad == "solicitud",
            Auditoria.registro_id == solicitud_id,
            Auditoria.campo == "estado",
        )
        .order_by(Auditoria.id)
    ).all()
    assert [
        (item.valor_anterior, item.valor_nuevo, item.accion)
        for item in auditorias
    ] == [
        ("RADICADA", "APROBADA", AccionAuditoria.UPDATE.value),
    ]

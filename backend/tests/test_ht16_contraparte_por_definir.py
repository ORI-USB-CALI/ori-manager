"""HT-16 (#172): Desbloquear revisión de contraparte 'Por definir' (HU-10 / HU-14)."""

import logging
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.core.config import settings
from backend.core.roles import CodigoRol
from backend.main import app
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.invitacion_revision_contraparte import (
    InvitacionRevisionContraparte,
)
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.schemas.convenio import ConvenioElaboracionActualizar
from backend.services.convenios import (
    ConvenioNoEditable,
    CorreoContraparteNoDisponible,
    ReferenciaConvenioInvalida,
    ServicioConvenios,
)
from backend.services.correo import ErrorEnvioCorreo, get_enviador_correo


@pytest.fixture(autouse=True)
def _configurar_url_publica(monkeypatch):
    if not settings.public_frontend_url:
        monkeypatch.setattr(
            settings, "public_frontend_url", "http://localhost:5173"
        )


def _crear_aliado(
    db,
    *,
    nombre: str = "Universidad Aliada",
    correo: str | None = "contraparte@aliada.edu.co",
    activo: bool = True,
) -> Aliado:
    aliado = Aliado(
        nombre=nombre,
        tipo="UNIVERSIDAD",
        tipo_identificacion="NIT",
        identificacion=str(uuid4().int)[:9],
        digito_verificacion="4",
        ciudad="Cali",
        correo=correo,
        activo=activo,
    )
    db.add(aliado)
    db.commit()
    db.refresh(aliado)
    return aliado


def _crear_convenio_manual_en_contraparte(
    client,
    db,
    gestor,
    crear_usuario,
    entrar_como,
    *,
    aliado_id: int | None = None,
    avales: int = 2,
) -> Convenio:
    entrar_como(gestor)
    tipo_id = db.scalar(
        select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO")
    )
    respuesta = client.post(
        "/api/convenios/manual",
        json={
            "aliado_id": aliado_id,
            "objeto": "Convenio manual para pruebas de HT-16",
            "tipo_convenio_id": tipo_id,
            "alcance": "INSTITUCIONAL",
            "duracion_meses": 12,
            "implicacion_financiera": "Sin costo",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    convenio = db.get(Convenio, respuesta.json()["id"])
    guardado = client.patch(
        f"/api/convenios/{convenio.id}/elaboracion",
        json={
            "expected_revision": 0,
            "contenido": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": convenio.objeto}],
                    }
                ],
            },
        },
    )
    assert guardado.status_code == 200, guardado.text
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, gestor)
    for _ in range(avales):
        revision = db.scalar(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.estado == "PENDIENTE",
            )
        )
        servicio.aprobar(
            convenio.id,
            revision.id,
            convenio.version_actual,
            crear_usuario(CodigoRol.REVISOR_ORI),
        )
    db.refresh(convenio)
    assert convenio.etapa_actual.codigo == ("REVISION_CONTRAPARTE" if avales == 2 else "REVISION_AVAL_JURIDICO")
    return convenio


# --- CA-01 y CA-03: Validación previa al envío y estado inequívoco ----------


def test_ca01_ca03_impide_envio_cuando_contraparte_esta_por_definir_sin_revision_fantasma(
    client, db, gestor, crear_usuario, entrar_como, correo_local
):
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=None
    )
    entrar_como(gestor)

    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )

    assert respuesta.status_code == 409
    assert "Por definir" in respuesta.json()["detail"]
    assert "aliado válido" in respuesta.json()["detail"]
    assert correo_local.mensajes == []
    revisiones_contraparte = db.scalars(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ).all()
    assert revisiones_contraparte == []


@pytest.mark.parametrize(
    ("correo", "activo", "dato_esperado"),
    [
        (None, True, "correo electrónico"),
        ("   ", True, "correo electrónico"),
        ("correo-invalido", True, "correo electrónico válido"),
        ("valido@aliada.edu.co", False, "estado activo"),
    ],
)
def test_ca01_impide_envio_cuando_faltan_datos_requeridos_en_contraparte(
    client,
    db,
    gestor,
    crear_usuario,
    entrar_como,
    correo_local,
    correo,
    activo,
    dato_esperado,
):
    aliado_inicial = _crear_aliado(db, correo=correo if activo else "ok@aliada.edu.co")
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado_inicial.id
    )
    if not activo or correo != aliado_inicial.correo:
        aliado_inicial.correo = correo
        aliado_inicial.activo = activo
        db.commit()

    entrar_como(gestor)
    detalle = client.get(f"/api/convenios/{convenio.id}")
    assert detalle.status_code == 200
    assert detalle.json()["aliado"]["correo"] == correo
    assert detalle.json()["aliado"]["activo"] is activo

    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )

    assert respuesta.status_code == 409
    assert dato_esperado in respuesta.json()["detail"]
    assert correo_local.mensajes == []
    assert (
        db.scalar(
            select(RevisionConvenio.id).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == "CONTRAPARTE",
            )
        )
        is None
    )


# --- CA-02, Tarea 1 y Tarea 4: Asignación, rectificación, permisos y auditoría -


@pytest.mark.parametrize(
    "rol_autorizado",
    [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI],
)
def test_ca02_asigna_y_rectifica_contraparte_antes_del_envio_con_auditoria_sin_crear_revision(
    client, db, gestor, crear_usuario, entrar_como, correo_local, rol_autorizado
):
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=None
    )
    aliado_sin_correo = _crear_aliado(db, nombre="Aliado Sin Correo", correo=None)
    aliado_valido = _crear_aliado(
        db, nombre="Aliado Definitivo", correo="juridica@definitivo.org"
    )
    actor = (
        gestor
        if rol_autorizado == CodigoRol.GESTOR_ORI
        else crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    )
    entrar_como(actor)

    # 1. Asignación inicial cuando estaba "Por definir"
    asignacion = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado_sin_correo.id},
    )
    assert asignacion.status_code == 200, asignacion.text
    assert asignacion.json()["aliado_id"] == aliado_sin_correo.id
    assert asignacion.json()["aliado"]["nombre"] == "Aliado Sin Correo"
    assert asignacion.json()["aliado"]["correo"] is None

    # 2. Rectificación a una contraparte con todos los datos requeridos
    rectificacion = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado_valido.id},
    )
    assert rectificacion.status_code == 200, rectificacion.text
    assert rectificacion.json()["aliado_id"] == aliado_valido.id
    assert rectificacion.json()["aliado"]["nombre"] == "Aliado Definitivo"
    assert rectificacion.json()["aliado"]["correo"] == "juridica@definitivo.org"

    # No se crea revisión de contraparte al guardar la contraparte
    revisiones_contraparte = db.scalars(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
        )
    ).all()
    assert revisiones_contraparte == []
    assert correo_local.mensajes == []

    # Registro en auditoría de ambos cambios
    registros = db.scalars(
        select(Auditoria)
        .where(
            Auditoria.entidad == "convenio",
            Auditoria.registro_id == convenio.id,
            Auditoria.accion == "UPDATE",
            Auditoria.campo == "aliado_id",
            Auditoria.etapa == "REVISION_CONTRAPARTE",
        )
        .order_by(Auditoria.id.asc())
    ).all()
    assert len(registros) == 2
    assert registros[0].valor_anterior is None
    assert registros[0].valor_nuevo == str(aliado_sin_correo.id)
    assert registros[0].evento == "CONTRAPARTE_ASIGNADA"
    assert registros[0].usuario_id == actor.id
    assert registros[0].rol == rol_autorizado.value
    assert registros[0].ejecucion == "HUMANA"

    assert registros[1].valor_anterior == str(aliado_sin_correo.id)
    assert registros[1].valor_nuevo == str(aliado_valido.id)
    assert registros[1].evento == "CONTRAPARTE_RECTIFICADA"
    assert registros[1].usuario_id == actor.id
    assert registros[1].rol == rol_autorizado.value

    # 3. Rectificar exige nueva versión y ambos avales, sin reescribir los previos.
    db.refresh(convenio)
    assert convenio.etapa_actual.codigo == "ELABORACION"
    version_anterior = convenio.version_actual
    bloqueado = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert bloqueado.status_code == 409
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, actor)
    assert convenio.version_actual == version_anterior + 1
    for instancia in (1, 2):
        revision = db.scalar(select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.tipo == "JURIDICA",
            RevisionConvenio.estado == "PENDIENTE",
        ))
        assert revision.instancia_juridica == instancia
        assert revision.numero_ronda == 2
        assert revision.snapshot_datos["aliado_id"] == aliado_valido.id
        servicio.aprobar(convenio.id, revision.id, convenio.version_actual,
                         crear_usuario(CodigoRol.REVISOR_ORI))
        if instancia == 1:
            assert client.post(
                f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                json={"expected_version": convenio.version_actual},
            ).status_code == 409
    envio = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert envio.status_code == 201, envio.text
    assert len(correo_local.mensajes) == 1
    assert correo_local.mensajes[0].destinatario == "juridica@definitivo.org"


@pytest.mark.parametrize(
    "rol_no_autorizado",
    [
        CodigoRol.REVISOR_ORI,
        CodigoRol.SOLICITANTE_INTERNO,
        CodigoRol.SOLICITANTE_EXTERNO,
    ],
)
def test_ca02_rechaza_modificacion_de_contraparte_por_falta_de_permisos(
    client, db, gestor, crear_usuario, entrar_como, rol_no_autorizado
):
    aliado_original = _crear_aliado(
        db, nombre="Aliado Original", correo="original@aliada.edu.co"
    )
    aliado_otro = _crear_aliado(
        db, nombre="Aliado Intruso", correo="intruso@aliada.edu.co"
    )
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado_original.id
    )
    intruso = crear_usuario(rol_no_autorizado)
    entrar_como(intruso)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado_otro.id},
    )
    assert respuesta.status_code == 403

    client.cookies.clear()
    sin_sesion = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado_otro.id},
    )
    assert sin_sesion.status_code == 401

    with pytest.raises(ConvenioNoEditable):
        ServicioConvenios(db).actualizar(
            convenio.id,
            ConvenioElaboracionActualizar(aliado_id=aliado_otro.id),
            intruso,
        )

    db.expire_all()
    assert db.get(Convenio, convenio.id).aliado_id == aliado_original.id


# --- CA-03 Escenario 2 y CA-05: Fallos de envío, idempotencia y reintentos --


def test_ca03_ca05_fallo_de_correo_no_crea_revision_fantasma_y_permite_reintentar(
    client, db, gestor, crear_usuario, entrar_como, correo_local, caplog
):
    caplog.set_level(logging.INFO, logger="backend.services.convenios")
    aliado = _crear_aliado(db, correo="contraparte@recuperable.org")
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id
    )
    entrar_como(gestor)

    class CorreoConFallo:
        def enviar(self, mensaje) -> None:
            raise ErrorEnvioCorreo("Servicio SMTP temporalmente no disponible")

    app.dependency_overrides[get_enviador_correo] = CorreoConFallo
    try:
        fallido = client.post(
            f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
            json={"expected_version": convenio.version_actual},
        )
    finally:
        app.dependency_overrides[get_enviador_correo] = lambda: correo_local

    assert fallido.status_code == 502
    assert "No fue posible enviar el correo" in fallido.json()["detail"]

    # No debe quedar revisión fantasma ni invitación huérfana
    db.expire_all()
    assert (
        db.scalar(
            select(RevisionConvenio.id).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == "CONTRAPARTE",
            )
        )
        is None
    )
    assert (
        db.scalar(
            select(InvitacionRevisionContraparte.id).join(
                RevisionConvenio,
                RevisionConvenio.id
                == InvitacionRevisionContraparte.revision_convenio_id,
            ).where(RevisionConvenio.convenio_id == convenio.id)
        )
        is None
    )

    # Reintento exitoso una vez restablecido el servicio
    reintento = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert reintento.status_code == 201, reintento.text
    assert len(correo_local.mensajes) == 1
    assert correo_local.mensajes[0].destinatario == "contraparte@recuperable.org"
    intentos = [r for r in caplog.records if r.msg.startswith("contraparte_correo_intento")]
    assert len(intentos) == 2
    assert len({r.intento_id for r in intentos}) == 2
    assert any(r.msg.startswith("contraparte_correo_fallido") for r in caplog.records)
    assert any(r.msg.startswith("contraparte_correo_confirmado") for r in caplog.records)

    # CA-05 Escenario 1: Solicitud repetida evita duplicar revisión e invitación
    duplicado = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert duplicado.status_code == 409
    assert "Ya existe una revisión de contraparte pendiente" in duplicado.json()["detail"]
    assert len(correo_local.mensajes) == 1


# --- CA-04 y CA-06: Integridad jurídica y cobertura por origen --------------


def test_ca04_ca06_protege_integridad_juridica_y_bloquea_cambios_no_permitidos(
    client, db, gestor, crear_usuario, entrar_como, convenio_listo
):
    aliado = _crear_aliado(db, correo="legal@aliada.edu.co")
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=None
    )
    entrar_como(gestor)

    # Los snapshots de las revisiones jurídicas aprobadas permanecen inmutables
    juridicas_antes = [
        (r.id, dict(r.snapshot_datos), dict(r.version_convenio.snapshot_metadata))
        for r in db.scalars(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == "JURIDICA",
            )
            .order_by(RevisionConvenio.id.asc())
        ).all()
    ]

    # En REVISION_CONTRAPARTE no se permite editar objeto ni otros metadatos congelados
    cambio_objeto = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"objeto": "Intento de alterar objeto aprobado"},
    )
    assert cambio_objeto.status_code == 409

    # En REVISION_CONTRAPARTE no se permite regresar aliado_id a None ("Por definir")
    cambio_nulo = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": None},
    )
    assert cambio_nulo.status_code == 422

    # Asignar contraparte válida preserva intactos los snapshots jurídicos previos
    asignado = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado.id},
    )
    assert asignado.status_code == 200
    db.expire_all()
    juridicas_despues = [
        (r.id, dict(r.snapshot_datos), dict(r.version_convenio.snapshot_metadata))
        for r in db.scalars(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == "JURIDICA",
            )
            .order_by(RevisionConvenio.id.asc())
        ).all()
    ]
    assert juridicas_despues == juridicas_antes

    # Un reintento de la asignación inicial es inocuo y no crea otra excepción.
    assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": aliado.id}).status_code == 200
    registros = list(db.scalars(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id,
        Auditoria.campo == "aliado_id", Auditoria.evento == "CONTRAPARTE_ASIGNADA",
    )))
    assert len(registros) == 1

    # Una vez enviada la revisión de contraparte, no se puede cambiar el aliado mientras esté pendiente
    envio = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert envio.status_code == 201
    otro_aliado = _crear_aliado(db, correo="otro@aliada.edu.co")
    bloqueado_en_curso = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": otro_aliado.id},
    )
    assert bloqueado_en_curso.status_code == 409

    # Para un convenio originado en SOLICITUD no se permite cambiar el aliado por PATCH
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio_listo.id, gestor)
    for _ in range(2):
        rev = db.scalar(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio_listo.id,
                RevisionConvenio.estado == "PENDIENTE",
            )
        )
        servicio.aprobar(
            convenio_listo.id,
            rev.id,
            convenio_listo.version_actual,
            crear_usuario(CodigoRol.REVISOR_ORI),
        )
    with pytest.raises(ReferenciaConvenioInvalida):
        servicio.actualizar(
            convenio_listo.id,
            ConvenioElaboracionActualizar(aliado_id=aliado.id),
            gestor,
        )


def test_ca03_ca05_reenvio_fallido_conserva_invitacion_activa_y_reintento_mantiene_trazabilidad(
    client, db, gestor, crear_usuario, entrar_como, correo_local
):
    aliado = _crear_aliado(db, correo="reenvio@recuperable.org")
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id
    )
    entrar_como(gestor)

    envio = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert envio.status_code == 201, envio.text
    revision_id = envio.json()["id"]
    invitacion_inicial_id = envio.json()["invitaciones_contraparte"][0]["id"]
    assert len(correo_local.mensajes) == 1

    class CorreoConFallo:
        def enviar(self, mensaje) -> None:
            raise ErrorEnvioCorreo("Fallo recuperable al reenviar invitación")

    app.dependency_overrides[get_enviador_correo] = CorreoConFallo
    try:
        fallo_reenvio = client.post(
            f"/api/convenios/{convenio.id}/revision-contraparte/{revision_id}/reenviar-invitacion",
            json={"expected_invitacion_id": invitacion_inicial_id},
        )
    finally:
        app.dependency_overrides[get_enviador_correo] = lambda: correo_local

    assert fallo_reenvio.status_code == 502
    assert "No fue posible enviar el correo" in fallo_reenvio.json()["detail"]

    # La invitación inicial sigue activa (no quedó revocada sin reemplazo) y no hay duplicadas
    db.expire_all()
    invitaciones_tras_fallo = db.scalars(
        select(InvitacionRevisionContraparte)
        .where(InvitacionRevisionContraparte.revision_convenio_id == revision_id)
        .order_by(InvitacionRevisionContraparte.id.asc())
    ).all()
    assert len(invitaciones_tras_fallo) == 1
    assert invitaciones_tras_fallo[0].id == invitacion_inicial_id
    assert invitaciones_tras_fallo[0].revocado_en is None
    assert invitaciones_tras_fallo[0].utilizado_en is None

    # Al reintentar tras recuperarse el servicio, se revoca la anterior y se crea la nueva con trazabilidad
    reintento_reenvio = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/{revision_id}/reenviar-invitacion",
        json={"expected_invitacion_id": invitacion_inicial_id},
    )
    assert reintento_reenvio.status_code == 200, reintento_reenvio.text
    assert len(correo_local.mensajes) == 2

    db.expire_all()
    invitaciones = db.scalars(
        select(InvitacionRevisionContraparte)
        .where(InvitacionRevisionContraparte.revision_convenio_id == revision_id)
        .order_by(InvitacionRevisionContraparte.id.asc())
    ).all()
    assert len(invitaciones) == 2
    assert invitaciones[0].id == invitacion_inicial_id
    assert invitaciones[0].revocado_en is not None
    assert invitaciones[0].generada_por_id == gestor.id
    assert invitaciones[1].revocado_en is None
    assert invitaciones[1].enviado_en is not None
    assert invitaciones[1].generada_por_id == gestor.id


def test_ca04_modificacion_de_contraparte_o_metadatos_congelados_exige_nueva_revision_juridica(
    client, db, gestor, crear_usuario, entrar_como, correo_local
):
    aliado_inicial = _crear_aliado(
        db, nombre="Aliado Inicial", correo="inicial@aliada.edu.co"
    )
    aliado_nuevo = _crear_aliado(
        db, nombre="Aliado Nuevo", correo="nuevo@aliada.edu.co"
    )
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado_inicial.id
    )
    entrar_como(gestor)

    # Si un dato congelado distinto al aliado cambia fuera del flujo normal, se bloquea el envío
    convenio.objeto = "Objeto alterado sin aval jurídico"
    db.commit()
    bloqueado_divergencia = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert bloqueado_divergencia.status_code == 409
    assert "requieren reiniciar la revisión jurídica" in bloqueado_divergencia.json()["detail"]

    # Restauramos el objeto congelado y enviamos a contraparte
    convenio.objeto = "Convenio manual para pruebas de HT-16"
    db.commit()
    envio = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert envio.status_code == 201, envio.text
    token = (
        correo_local.mensajes[-1]
        .texto.split("/revision-contraparte#token=", 1)[1]
        .splitlines()[0]
    )

    # La contraparte devuelve el convenio con observaciones -> regresa a ELABORACION
    client.cookies.clear()
    devolucion = client.post(
        "/api/public/revision-contraparte/devolver",
        json={
            "token": token,
            "nombre_firmante": "Representante Legal",
            "cargo_firmante": "Rector",
            "observaciones": ["Se requiere ajustar la contraparte del convenio"],
        },
    )
    assert devolucion.status_code == 200, devolucion.text

    entrar_como(gestor)
    historial = client.get(f"/api/convenios/{convenio.id}/revisiones").json()
    revision_devuelta = next(
        r for r in historial["revisiones"] if r["tipo"] == "CONTRAPARTE"
    )
    observacion_id = revision_devuelta["observaciones"][0]["id"]
    atender = client.patch(
        f"/api/convenios/{convenio.id}/observaciones/{observacion_id}/atender",
        json={"respuesta": "Se actualiza la contraparte y se reenvía a Jurídica"},
    )
    assert atender.status_code == 200, atender.text

    # En ELABORACION se cambia la contraparte (metadato congelado en CAMPOS_SNAPSHOT)
    version_anterior = convenio.version_actual
    cambio_contraparte = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"aliado_id": aliado_nuevo.id},
    )
    assert cambio_contraparte.status_code == 200, cambio_contraparte.text

    # Al finalizar la elaboración, el cambio en aliado_id genera nueva versión e inicia nueva ronda jurídica
    finalizado = client.post(
        f"/api/convenios/{convenio.id}/elaboracion/finalizar"
    )
    assert finalizado.status_code == 200, finalizado.text
    db.expire_all()
    convenio = db.get(Convenio, convenio.id)
    assert convenio.version_actual == version_anterior + 1
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"

    nueva_juridica = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.tipo == "JURIDICA",
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    assert nueva_juridica is not None
    assert nueva_juridica.numero_ronda == 2
    assert nueva_juridica.instancia_juridica == 1
    assert nueva_juridica.snapshot_datos["aliado_id"] == aliado_nuevo.id

    # Los avales jurídicos de la versión anterior no permiten enviar a contraparte sin aprobar la nueva ronda
    intento_envio_sin_aval = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert intento_envio_sin_aval.status_code == 409


@pytest.mark.parametrize("caso", ["inexistente", "inactivo"])
def test_asignacion_rechaza_aliado_invalido_sin_cambiar_estado(
    client, db, gestor, crear_usuario, entrar_como, caso,
):
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como,
    )
    aliado = _crear_aliado(db, activo=False)
    aliado_id = aliado.id if caso == "inactivo" else 2147483647
    respuesta = client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": aliado_id})
    assert respuesta.status_code == 422
    db.refresh(convenio)
    assert convenio.aliado_id is None
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"


@pytest.mark.parametrize("frozen", ["version", "RJ1", "RJ2", "sin_asignacion_auditada"])
def test_asignacion_inicial_no_omite_contraparte_identificada_en_ningun_aval(
    client, db, gestor, crear_usuario, entrar_como, correo_local, frozen,
):
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como,
    )
    aliado = _crear_aliado(db)
    otro = _crear_aliado(db)
    if frozen == "sin_asignacion_auditada":
        convenio.aliado_id = aliado.id
    else:
        assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": aliado.id}).status_code == 200
        juridicas = list(db.scalars(select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.tipo == "JURIDICA",
        ).order_by(RevisionConvenio.instancia_juridica)))
        if frozen == "version":
            version = juridicas[0].version_convenio
            version.snapshot_metadata = {**version.snapshot_metadata, "aliado_id": otro.id}
        else:
            revision = juridicas[0 if frozen == "RJ1" else 1]
            revision.snapshot_datos = {**revision.snapshot_datos, "aliado_id": otro.id}
    db.commit()
    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                            json={"expected_version": convenio.version_actual})
    assert respuesta.status_code == 409
    detalle = respuesta.json()["detail"]
    assert "reiniciar la revisión jurídica" in (detalle["message"] if isinstance(detalle, dict) else detalle)
    assert not correo_local.mensajes


def test_rectificar_contraparte_avalada_retorna_elaboracion_y_repetir_no_duplica_historial(
    client, db, gestor, crear_usuario, entrar_como, correo_local,
):
    original = _crear_aliado(db)
    otro = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=original.id,
    )
    for _ in range(2):
        assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": otro.id}).status_code == 200
    historial = client.get(f"/api/convenios/{convenio.id}/revisiones").json()
    retornos = [h for h in historial["cambios_etapa"] if h["observacion"] and "Rectificación" in h["observacion"]]
    assert len(retornos) == 1
    juridicas = [r for r in historial["revisiones"] if r["tipo"] == "JURIDICA"]
    assert len(juridicas) == 2
    assert all(r["snapshot_datos"]["aliado_id"] == original.id for r in juridicas)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 409
    assert not correo_local.mensajes


@pytest.mark.parametrize("falta", ["correo", "url"])
def test_servicio_manual_no_confirma_revision_sin_servicio_de_correo(
    client, db, gestor, crear_usuario, entrar_como, correo_local, falta,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id,
    )
    servicio = ServicioConvenios(db, enviador=correo_local if falta == "url" else None,
                                frontend_url=None if falta == "url" else "http://localhost:5173")
    with pytest.raises(CorreoContraparteNoDisponible):
        servicio.enviar_a_contraparte(convenio.id, convenio.version_actual, gestor)
    assert db.scalar(select(RevisionConvenio.id).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.tipo == "CONTRAPARTE",
    )) is None
    assert not correo_local.mensajes


@pytest.mark.parametrize("reenviar", [False, True])
def test_correo_aceptado_con_commit_fallido_no_habilita_enlace_y_se_recupera(
    client, db, gestor, crear_usuario, entrar_como, correo_local, monkeypatch, caplog, reenviar,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id,
    )
    ruta = f"/api/convenios/{convenio.id}/revision-contraparte/enviar"
    cuerpo = {"expected_version": convenio.version_actual}
    if reenviar:
        inicial = client.post(ruta, json=cuerpo)
        assert inicial.status_code == 201
        invitacion_previa_id = inicial.json()["invitaciones_contraparte"][0]["id"]
        ruta = f"/api/convenios/{convenio.id}/revision-contraparte/{inicial.json()['id']}/reenviar-invitacion"
        cuerpo = {"expected_invitacion_id": invitacion_previa_id}
    def fallo_commit():
        raise SQLAlchemyError("Commit fallido simulado")
    with monkeypatch.context() as cambio:
        cambio.setattr(db, "commit", fallo_commit)
        with caplog.at_level(logging.INFO, logger="backend.services.convenios"):
            fallido = client.post(ruta, json=cuerpo)
    assert fallido.status_code == 503
    token_fallido = correo_local.mensajes[-1].texto.split("#token=", 1)[1].splitlines()[0]
    assert client.post("/api/public/revision-contraparte/acceso", json={"token": token_fallido}).status_code == 400
    registros = [r for r in caplog.records if r.msg.startswith("contraparte_correo_")]
    assert any(r.msg.startswith("contraparte_correo_aceptado") for r in registros)
    assert any(r.msg.startswith("contraparte_correo_commit_no_confirmado") for r in registros)
    assert len({r.intento_id for r in registros}) == 1
    assert token_fallido not in caplog.text
    if reenviar:
        previa = db.get(InvitacionRevisionContraparte, invitacion_previa_id)
        assert previa.revocado_en is None
    reintento = client.post(ruta, json=cuerpo)
    assert reintento.status_code == (200 if reenviar else 201), reintento.text
    nuevo_token = correo_local.mensajes[-1].texto.split("#token=", 1)[1].splitlines()[0]
    assert nuevo_token != token_fallido
    assert client.post("/api/public/revision-contraparte/acceso", json={"token": nuevo_token}).status_code == 200


def test_reenvio_repetido_con_misma_invitacion_no_duplica_correos(
    client, db, gestor, crear_usuario, entrar_como, correo_local,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id,
    )
    inicial = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                          json={"expected_version": convenio.version_actual}).json()
    ruta = f"/api/convenios/{convenio.id}/revision-contraparte/{inicial['id']}/reenviar-invitacion"
    cuerpo = {"expected_invitacion_id": inicial["invitaciones_contraparte"][0]["id"]}
    assert client.post(ruta, json=cuerpo).status_code == 200
    repetido = client.post(ruta, json=cuerpo)
    assert repetido.status_code == 409
    assert len(correo_local.mensajes) == 2
    assert len(list(db.scalars(select(InvitacionRevisionContraparte).where(
        InvitacionRevisionContraparte.revision_convenio_id == inicial["id"],
        InvitacionRevisionContraparte.revocado_en.is_(None),
    )))) == 1


@pytest.mark.parametrize("rol", [CodigoRol.REVISOR_ORI, CodigoRol.SOLICITANTE_INTERNO, CodigoRol.SOLICITANTE_EXTERNO])
def test_envio_y_reenvio_rechazan_roles_sin_permiso(
    client, db, gestor, crear_usuario, entrar_como, correo_local, rol,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id,
    )
    entrar_como(crear_usuario(rol))
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 403
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/1/reenviar-invitacion",
                       json={"expected_invitacion_id": 1}).status_code == 403
    assert not correo_local.mensajes


def test_api_sin_url_publica_responde_503_sin_crear_revision(
    client, db, gestor, crear_usuario, entrar_como, correo_local, monkeypatch,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id,
    )
    monkeypatch.setattr(settings, "public_frontend_url", None)
    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                            json={"expected_version": convenio.version_actual})
    assert respuesta.status_code == 503
    assert not correo_local.mensajes
    assert db.scalar(select(RevisionConvenio.id).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.tipo == "CONTRAPARTE",
    )) is None


def test_recupera_rectificacion_heredada_sin_reutilizar_el_aval_anterior(
    client, db, gestor, crear_usuario, entrar_como, correo_local,
):
    original = _crear_aliado(db)
    nuevo = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=original.id,
    )
    # Estado que podía dejar la implementación auditada: metadato cambiado
    # después de los avales, sin nueva versión ni ronda jurídica.
    convenio.aliado_id = nuevo.id
    db.commit()
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 409
    assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": nuevo.id}).status_code == 200
    db.refresh(convenio)
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert not correo_local.mensajes


def test_fallo_commit_al_rectificar_revierte_aliado_y_transicion(
    client, db, gestor, crear_usuario, entrar_como, monkeypatch,
):
    original = _crear_aliado(db)
    nuevo = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(
        client, db, gestor, crear_usuario, entrar_como, aliado_id=original.id,
    )
    def fallo_commit():
        raise SQLAlchemyError("Commit fallido simulado")
    with monkeypatch.context() as cambio:
        cambio.setattr(db, "commit", fallo_commit)
        with pytest.raises(SQLAlchemyError):
            ServicioConvenios(db).actualizar(convenio.id,
                ConvenioElaboracionActualizar(aliado_id=nuevo.id), gestor)
    db.refresh(convenio)
    assert convenio.aliado_id == original.id
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    historial = client.get(f"/api/convenios/{convenio.id}/revisiones").json()
    assert not any(h["observacion"] and "Rectificación" in h["observacion"] for h in historial["cambios_etapa"])


CAMBIOS_IDENTIDAD = [
    ("nombre", "Nueva razón social"), ("tipo", "COLEGIO"),
    ("tipo_identificacion", "OTRO"), ("identificacion", "900888777"),
    ("digito_verificacion", "7"),
]


def _avalar_identidad(db, convenio, gestor, crear_usuario):
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, gestor)
    for _ in range(2):
        revision = db.scalar(select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.estado == "PENDIENTE",
        ))
        servicio.aprobar(convenio.id, revision.id, convenio.version_actual, crear_usuario(CodigoRol.REVISOR_ORI))


@pytest.mark.parametrize("origen", ["MANUAL_ORI", "SOLICITUD"])
@pytest.mark.parametrize(("campo", "valor"), CAMBIOS_IDENTIDAD)
def test_identidad_modificada_con_mismo_id_exige_nueva_ronda_y_preserva_avales(
    client, db, gestor, crear_usuario, entrar_como, correo_local, convenio_listo, origen, campo, valor,
):
    aliado = _crear_aliado(db)
    if origen == "MANUAL_ORI":
        convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id)
    else:
        convenio = convenio_listo
        convenio.aliado_id = aliado.id
        convenio.solicitud.aliado_id = aliado.id
        db.commit()
        _avalar_identidad(db, convenio, gestor, crear_usuario)
    juridicas = list(db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.tipo == "JURIDICA",
    )))
    congelado = dict(juridicas[0].snapshot_datos["aliado_identidad"])
    assert set(congelado) == {"nombre", "tipo", "tipo_identificacion", "identificacion", "digito_verificacion"}
    if campo == "tipo_identificacion":
        aliado.digito_verificacion = None
    setattr(aliado, campo, valor)
    db.commit()
    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                            json={"expected_version": convenio.version_actual})
    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["codigo"] == "IDENTIDAD_ALIADO_CAMBIADA"
    assert not correo_local.mensajes
    assert all(r.snapshot_datos["aliado_identidad"] == congelado for r in juridicas)
    version_previa = convenio.version_actual
    reabrir = client.post(f"/api/convenios/{convenio.id}/revision-juridica/reabrir-por-identidad",
                         json={"expected_version": version_previa})
    assert reabrir.status_code == 200, reabrir.text
    assert convenio.etapa_actual.codigo == "ELABORACION"
    _avalar_identidad(db, convenio, gestor, crear_usuario)
    assert convenio.version_actual == version_previa + 1
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 201
    assert all(r.snapshot_datos["aliado_identidad"] == congelado for r in juridicas)
    actual = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.numero_ronda == 2,
        RevisionConvenio.instancia_juridica == 2,
    ))
    assert actual.snapshot_datos["aliado_identidad"][campo] == valor


@pytest.mark.parametrize("avales", [0, 1])
@pytest.mark.parametrize(("campo", "valor"), CAMBIOS_IDENTIDAD)
def test_rj1_y_rj2_no_aprueban_una_identidad_distinta_a_la_presentada(
    client, db, gestor, crear_usuario, entrar_como, campo, valor, avales,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como,
                                                   aliado_id=aliado.id, avales=avales)
    pendiente = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.estado == "PENDIENTE",
    ))
    if campo == "tipo_identificacion":
        aliado.digito_verificacion = None
    setattr(aliado, campo, valor)
    db.commit()
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))
    respuesta = client.post(f"/api/convenios/{convenio.id}/revisiones/{pendiente.id}/aprobar",
                            json={"expected_version": convenio.version_actual})
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["detail"]["codigo"] == "IDENTIDAD_ALIADO_CAMBIADA"
    db.refresh(pendiente)
    assert pendiente.estado == "PENDIENTE"
    assert pendiente.resultado is None


def test_excepcion_inicial_no_autoriza_editar_posteriormente_la_identidad_compartida(
    client, db, gestor, crear_usuario, entrar_como, correo_local,
):
    convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como)
    aliado = _crear_aliado(db)
    assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": aliado.id}).status_code == 200
    huella = db.scalar(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id,
        Auditoria.campo == "aliado_identidad_sha256",
    ))
    assert len(huella.valor_nuevo) == 64
    # Se conserva la edición normal del catálogo, sin veto por avales compartidos.
    assert client.patch(f"/api/aliados/{aliado.id}", json={"nombre": "Razón social rectificada"}).status_code == 200
    envio = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                        json={"expected_version": convenio.version_actual})
    assert envio.status_code == 409
    assert envio.json()["detail"]["codigo"] == "IDENTIDAD_ALIADO_CAMBIADA"
    assert not correo_local.mensajes
    assert client.patch(f"/api/convenios/{convenio.id}", json={"aliado_id": aliado.id}).status_code == 200
    assert convenio.etapa_actual.codigo == "ELABORACION"
    _avalar_identidad(db, convenio, gestor, crear_usuario)
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 201


@pytest.mark.parametrize("cuerpo", [None, {}, {"expected_invitacion_id": None}, {"expected_invitacion_id": 0}])
def test_reenvio_exige_identificador_http_sin_efectos_secundarios(
    client, db, gestor, crear_usuario, entrar_como, correo_local, cuerpo,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id)
    inicial = client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                          json={"expected_version": convenio.version_actual}).json()
    ruta = f"/api/convenios/{convenio.id}/revision-contraparte/{inicial['id']}/reenviar-invitacion"
    assert client.post(ruta, **({"json": cuerpo} if cuerpo is not None else {})).status_code == 422
    assert len(correo_local.mensajes) == 1
    assert len(list(db.scalars(select(InvitacionRevisionContraparte).where(
        InvitacionRevisionContraparte.revision_convenio_id == inicial["id"],
    )))) == 1


@pytest.mark.parametrize("caso", ["sin_cambios", "revision_pendiente", "version_obsoleta", "rol_sin_permiso"])
def test_reapertura_por_identidad_respeta_etapa_permisos_y_version(
    client, db, gestor, crear_usuario, entrar_como, correo_local, caso,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id)
    if caso == "revision_pendiente":
        assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                           json={"expected_version": convenio.version_actual}).status_code == 201
    if caso != "sin_cambios":
        aliado.nombre = "Identidad modificada"
        db.commit()
    if caso == "rol_sin_permiso":
        entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))
    respuesta = client.post(f"/api/convenios/{convenio.id}/revision-juridica/reabrir-por-identidad",
                            json={"expected_version": convenio.version_actual - (caso == "version_obsoleta")})
    assert respuesta.status_code == (403 if caso == "rol_sin_permiso" else 409)
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"


def test_snapshot_sin_identidad_exige_nueva_version_sin_reescribir_el_historico(
    client, db, gestor, crear_usuario, entrar_como,
):
    aliado = _crear_aliado(db)
    convenio = _crear_convenio_manual_en_contraparte(client, db, gestor, crear_usuario, entrar_como, aliado_id=aliado.id)
    version = ServicioConvenios(db)._version_actual(convenio)
    historico = {k: v for k, v in version.snapshot_metadata.items() if k != "aliado_identidad"}
    version.snapshot_metadata = historico
    db.commit()
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 409
    previa = convenio.version_actual
    assert client.post(f"/api/convenios/{convenio.id}/revision-juridica/reabrir-por-identidad",
                       json={"expected_version": previa}).status_code == 200
    _avalar_identidad(db, convenio, gestor, crear_usuario)
    assert convenio.version_actual == previa + 1
    assert version.snapshot_metadata == historico
    assert client.post(f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
                       json={"expected_version": convenio.version_actual}).status_code == 201

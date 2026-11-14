# ruff: noqa: EXE002
"""HT-16 (#172): Desbloquear revisión de contraparte 'Por definir' (HU-10 / HU-14)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

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
    for _ in range(2):
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
    assert convenio.etapa_actual.codigo == "REVISION_CONTRAPARTE"
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
    assert registros[1].evento == "CONTRAPARTE_ASIGNADA"
    assert registros[1].usuario_id == actor.id
    assert registros[1].rol == rol_autorizado.value

    # 3. Una vez asignada una contraparte válida, el envío se desbloquea
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
    client, db, gestor, crear_usuario, entrar_como, correo_local
):
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
            f"/api/convenios/{convenio.id}/revision-contraparte/{revision_id}/reenviar-invitacion"
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
        f"/api/convenios/{convenio.id}/revision-contraparte/{revision_id}/reenviar-invitacion"
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

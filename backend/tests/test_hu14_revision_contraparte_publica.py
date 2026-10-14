"""El enlace público de HU-10 solo habilita la contraparte de convenios manuales."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.respuesta_revision_contraparte import RespuestaRevisionContraparte
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.services.contraparte_externa import crear_invitacion_contraparte
from backend.services.convenios import ServicioConvenios

ACCIONES = ("acceso", "aprobar", "devolver")
FIRMA_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _datos(accion, token):
    datos = {"token": token}
    if accion != "acceso":
        datos.update(nombre_firmante="Representante", cargo_firmante="Director")
    if accion == "aprobar":
        datos["firma"] = FIRMA_PNG
    if accion == "devolver":
        datos["observaciones"] = ["Ajustar el alcance"]
    return datos


def _avalar(db, convenio, gestor, crear_usuario):
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, gestor)
    for _ in range(2):
        revision = db.scalar(select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        ))
        servicio.aprobar(
            convenio.id, revision.id, convenio.version_actual,
            crear_usuario(CodigoRol.REVISOR_ORI),
        )


@pytest.fixture
def enlace_manual(client, db, gestor, crear_usuario, correo_local):
    aliado = Aliado(
        nombre="Contraparte manual", tipo="UNIVERSIDAD",
        tipo_identificacion="NIT", identificacion=uuid4().hex,
        ciudad="Cali", correo="contraparte@example.com",
    )
    db.add(aliado)
    db.commit()
    respuesta = client.post("/api/convenios/manual", json={
        "aliado_id": aliado.id,
        "objeto": "Contenido reservado del convenio manual",
        "tipo_convenio_id": db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO")),
        "alcance": "INSTITUCIONAL", "duracion_meses": 12,
        "implicacion_financiera": "Sin costo",
    })
    assert respuesta.status_code == 201, respuesta.text
    convenio = db.get(Convenio, respuesta.json()["id"])
    assert convenio.solicitud_id is None
    assert convenio.origen == "MANUAL_ORI"
    guardado = client.patch(f"/api/convenios/{convenio.id}/elaboracion", json={
        "expected_version": convenio.version_actual,
        "contenido": {"type": "doc", "content": [{
            "type": "paragraph", "content": [{"type": "text", "text": convenio.objeto}],
        }]},
    })
    assert guardado.status_code == 200, guardado.text
    _avalar(db, convenio, gestor, crear_usuario)
    juridicas = db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.tipo == "JURIDICA",
    )).all()
    assert len(juridicas) == 2
    assert all(r.snapshot_datos["origen"] == "MANUAL_ORI" for r in juridicas)
    assert all(r.version_convenio.snapshot_metadata["origen"] == "MANUAL_ORI" for r in juridicas)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )
    assert respuesta.status_code == 201, respuesta.text
    revision = db.get(RevisionConvenio, respuesta.json()["id"])
    invitacion = revision.invitaciones_contraparte[0]
    mensaje = correo_local.mensajes[-1]
    token = mensaje.texto.split("/revision-contraparte#token=", 1)[1].splitlines()[0]
    assert mensaje.destinatario == aliado.correo
    assert not mensaje.cc
    assert len(token) == 64
    assert invitacion.token_hash == sha256(token.encode()).hexdigest()
    assert invitacion.token_hash != token
    assert timedelta(minutes=59) < invitacion.expira_en - datetime.now(UTC) <= timedelta(hours=1)
    client.cookies.clear()
    return convenio, revision, invitacion, token


def _estado(db, convenio, revision, invitacion):
    db.expire_all()
    modelos = (HistorialEtapa, ObservacionRevision, RespuestaRevisionContraparte, RevisionConvenio)
    return (
        convenio.etapa_actual_id, convenio.version_actual,
        revision.estado, revision.resultado, revision.version_resultado_id,
        invitacion.utilizado_en, invitacion.revocado_en,
        tuple(db.scalar(select(func.count()).select_from(modelo)) for modelo in modelos),
    )


@pytest.mark.parametrize("accion", ACCIONES)
@pytest.mark.parametrize("caso,codigo", [
    ("ausente", None), ("vacio", None), ("corto", None),
    ("invalido", "ENLACE_INVALIDO"),
    ("caducado", "ENLACE_EXPIRADO"),
    ("revocado", "ENLACE_NO_DISPONIBLE"),
    ("utilizado", "ENLACE_NO_DISPONIBLE"),
    ("resuelta", "ENLACE_NO_DISPONIBLE"),
    ("otra_etapa", "ENLACE_NO_DISPONIBLE"),
    ("otra_version", "ENLACE_NO_DISPONIBLE"),
])
def test_enlace_inhabilitado_no_expone_contenido_ni_permite_decisiones(
    client, db, enlace_manual, accion, caso, codigo,
):
    convenio, revision, invitacion, token = enlace_manual
    if caso == "caducado":
        invitacion.expira_en = datetime.now(UTC) - timedelta(seconds=1)
    elif caso == "revocado":
        invitacion.revocado_en = datetime.now(UTC)
    elif caso == "utilizado":
        invitacion.utilizado_en = datetime.now(UTC)
    elif caso == "resuelta":
        revision.estado = "RESUELTA"
        revision.resultado = "APROBADA"
    elif caso == "otra_etapa":
        convenio.etapa_actual = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    elif caso == "otra_version":
        convenio.version_actual += 1
    db.commit()
    token = {"invalido": "x" * 64, "vacio": "", "corto": "x"}.get(caso, token)
    datos = _datos(accion, token)
    if caso == "ausente":
        del datos["token"]
    antes = _estado(db, convenio, revision, invitacion)
    respuesta = client.post(f"/api/public/revision-contraparte/{accion}", json=datos)
    assert respuesta.status_code == (422 if codigo is None else 400), respuesta.text
    if codigo is None:
        assert respuesta.json()["detail"][0]["loc"] == ["body", "token"]
    else:
        assert respuesta.json() == {"detail": {"codigo": codigo}}
    assert "contenido" not in respuesta.json()
    assert _estado(db, convenio, revision, invitacion) == antes


@pytest.mark.parametrize("accion", ["aprobar", "devolver"])
def test_token_manual_valido_permite_una_decision_y_no_se_reutiliza(
    client, db, enlace_manual, accion,
):
    convenio, revision, invitacion, token = enlace_manual
    acceso = client.post("/api/public/revision-contraparte/acceso", json={"token": token})
    assert acceso.status_code == 200, acceso.text
    assert acceso.json()["contenido"] == revision.version_convenio.contenido
    assert acceso.json()["contraparte"] == convenio.aliado.nombre
    assert acceso.json()["version_numero"] == convenio.version_actual
    respuesta = client.post(f"/api/public/revision-contraparte/{accion}", json=_datos(accion, token))
    assert respuesta.status_code == 200, respuesta.text
    resultado = "APROBADA" if accion == "aprobar" else "DEVUELTA"
    assert respuesta.json() == {"estado": "RESUELTA", "resultado": resultado}
    db.expire_all()
    assert invitacion.utilizado_en is not None
    assert revision.resuelta_por_id is None
    assert revision.respuesta_contraparte.correo_actor == convenio.aliado.correo
    assert convenio.etapa_actual.codigo == ("REVISION_FINAL" if accion == "aprobar" else "ELABORACION")
    finales = db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id, RevisionConvenio.tipo == "FINAL",
    )).all()
    assert len(finales) == (1 if accion == "aprobar" else 0)
    if finales:
        assert finales[0].version_convenio_id == revision.version_convenio_id
    antes = _estado(db, convenio, revision, invitacion)
    for intento in ACCIONES:
        replay = client.post(f"/api/public/revision-contraparte/{intento}", json=_datos(intento, token))
        assert replay.status_code == 400
        assert replay.json() == {"detail": {"codigo": "ENLACE_NO_DISPONIBLE"}}
    assert _estado(db, convenio, revision, invitacion) == antes


@pytest.mark.parametrize("accion", ACCIONES)
def test_enlace_historico_de_solicitud_no_reactiva_el_flujo_publico(
    client, db, gestor, crear_usuario, convenio_listo, accion,
):
    _avalar(db, convenio_listo, gestor, crear_usuario)
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, convenio_listo.version_actual, gestor,
    )
    # Representa un enlace de la implementación previa al FIX de HU-14 (#102).
    invitacion, token = crear_invitacion_contraparte(
        db, revision, "contraparte@example.com", None, gestor.id,
    )
    db.commit()
    client.cookies.clear()
    antes = _estado(db, convenio_listo, revision, invitacion)
    respuesta = client.post(f"/api/public/revision-contraparte/{accion}", json=_datos(accion, token))
    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json() == {"detail": {"codigo": "ENLACE_NO_DISPONIBLE"}}
    assert _estado(db, convenio_listo, revision, invitacion) == antes


def test_reenvio_manual_revoca_el_token_anterior(
    client, db, enlace_manual, gestor, entrar_como, correo_local,
):
    convenio, revision, invitacion, token = enlace_manual
    entrar_como(gestor)
    respuesta = client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/{revision.id}/reenviar-invitacion",
    )
    assert respuesta.status_code == 200, respuesta.text
    nuevo_token = correo_local.mensajes[-1].texto.split("#token=", 1)[1].splitlines()[0]
    assert nuevo_token != token
    db.refresh(invitacion)
    assert invitacion.revocado_en is not None
    client.cookies.clear()
    antes = _estado(db, convenio, revision, invitacion)
    for accion in ACCIONES:
        rechazada = client.post(f"/api/public/revision-contraparte/{accion}", json=_datos(accion, token))
        assert rechazada.status_code == 400
        assert rechazada.json() == {"detail": {"codigo": "ENLACE_NO_DISPONIBLE"}}
    assert _estado(db, convenio, revision, invitacion) == antes
    acceso = client.post("/api/public/revision-contraparte/acceso", json={"token": nuevo_token})
    assert acceso.status_code == 200, acceso.text

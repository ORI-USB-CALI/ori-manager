from io import BytesIO
from uuid import uuid4

from sqlalchemy import select

# tests/ no es paquete; con el modo de import por defecto de pytest (prepend),
# el directorio tests/ está en sys.path.
from test_hu07_revision_solicitudes import _datos_completos

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.pais import Pais
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio


def _radicar_nueva(client, db) -> int:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    pais_id = db.scalar(select(Pais.id).where(Pais.codigo_iso == "CO"))
    creada = client.post("/api/solicitudes", json=_datos_completos(tipo.id, pais_id))
    assert creada.status_code == 201, creada.text
    solicitud_id = creada.json()["id"]
    documento = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": "RUT"},
        files={"archivo": ("rut.pdf", BytesIO(b"%PDF-1.4 rut"), "application/pdf")},
    )
    assert documento.status_code == 201, documento.text
    radicada = client.post(f"/api/solicitudes/{solicitud_id}/radicar")
    assert radicada.status_code == 200, radicada.text
    return solicitud_id


def _escenario(client, db, crear_usuario, entrar_como):
    solicitante = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    solicitante.documento_identidad = "CE-123"
    solicitante.entidad_externa = "Fundación Solicitante"
    db.commit()
    gestor = crear_usuario(CodigoRol.GESTOR_ORI)
    entrar_como(solicitante)
    return solicitante, gestor, _radicar_nueva(client, db)


def _devolver(client, solicitud_id: int, observaciones: str) -> None:
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": observaciones},
    )
    assert respuesta.status_code == 200, respuesta.text


def test_ca05_devolucion_queda_relacionada_con_la_version_corregida(
    client, db, crear_usuario, entrar_como
):
    solicitante, gestor, solicitud_id = _escenario(
        client, db, crear_usuario, entrar_como
    )
    entrar_como(gestor)
    _devolver(client, solicitud_id, "Ajustar el objeto")
    entrar_como(solicitante)
    client.patch(f"/api/solicitudes/{solicitud_id}", json={"objeto": "Objeto corregido"})
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    respuesta = client.get(f"/api/solicitudes/{solicitud_id}/historial")

    assert respuesta.status_code == 200, respuesta.text
    v1, v2 = respuesta.json()["versiones"]
    assert v1["numero"] == 1
    assert v1["devolucion"]["observaciones"] == "Ajustar el objeto"
    assert v1["devolucion"]["corregida_en_version"] == 2
    assert v1["devolucion"]["devuelta_por_nombre"] == gestor.nombre_completo
    assert v2["numero"] == 2
    assert v2["devolucion"] is None


def test_cada_devolucion_conserva_sus_propias_observaciones(
    client, db, crear_usuario, entrar_como
):
    solicitante, gestor, solicitud_id = _escenario(
        client, db, crear_usuario, entrar_como
    )
    for observaciones in ("Primera devolución", "Segunda devolución"):
        entrar_como(gestor)
        _devolver(client, solicitud_id, observaciones)
        entrar_como(solicitante)
        assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    entrar_como(gestor)
    respuesta = client.get(f"/api/solicitudes/recibidas/{solicitud_id}/historial")

    assert respuesta.status_code == 200, respuesta.text
    devoluciones = [
        (version["numero"], version["devolucion"] and version["devolucion"]["observaciones"])
        for version in respuesta.json()["versiones"]
    ]
    assert devoluciones == [
        (1, "Primera devolución"),
        (2, "Segunda devolución"),
        (3, None),
    ]


def test_devolucion_pendiente_de_correccion_no_apunta_a_version(
    client, db, crear_usuario, entrar_como
):
    _, gestor, solicitud_id = _escenario(client, db, crear_usuario, entrar_como)
    entrar_como(gestor)
    _devolver(client, solicitud_id, "Falta el RUT vigente")

    respuesta = client.get(f"/api/solicitudes/recibidas/{solicitud_id}/historial")

    assert respuesta.status_code == 200, respuesta.text
    (v1,) = respuesta.json()["versiones"]
    assert v1["devolucion"]["corregida_en_version"] is None


def test_historial_ajeno_es_404(client, db, crear_usuario, entrar_como):
    _, _, solicitud_id = _escenario(client, db, crear_usuario, entrar_como)
    entrar_como(crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO))
    assert client.get(f"/api/solicitudes/{solicitud_id}/historial").status_code == 404


def test_solicitante_no_consulta_historial_por_la_ruta_de_ori(
    client, db, crear_usuario, entrar_como
):
    _, _, solicitud_id = _escenario(client, db, crear_usuario, entrar_como)
    respuesta = client.get(f"/api/solicitudes/recibidas/{solicitud_id}/historial")
    assert respuesta.status_code == 403


def test_devolver_sin_version_no_falla(client, db, gestor, crear_usuario):
    # Solicitud radicada antes de HT-02: no tiene filas en solicitud_version.
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex[:12]}",
        tipo_solicitante=TipoSolicitante.INTERNO.value,
        solicitante_id=crear_usuario(CodigoRol.SOLICITANTE_INTERNO).id,
        estado=EstadoSolicitud.RADICADA.value,
    )
    db.add(solicitud)
    db.commit()

    _devolver(client, solicitud.id, "Completar información")

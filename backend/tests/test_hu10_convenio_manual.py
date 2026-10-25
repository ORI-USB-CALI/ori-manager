"""HU-10 — creación desde la ORI sin solicitud; integración sobre rama HT-03."""
from copy import deepcopy

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import ContextoVersionConvenio, TipoRevisionConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.version_convenio import VersionConvenio


def _crear(client, **datos):
    return client.post("/api/convenios/manual", json=datos)


RESERVADOS = {
    "convenio_origen_id": 1,
    "numero_renovacion": 3,
    "fecha_firma": "2026-10-13",
    "porcentaje_avance": 100,
}
CASOS_RESERVADOS = [
    pytest.param({campo: valor}, id=campo) for campo, valor in RESERVADOS.items()
] + [
    pytest.param({campo: None}, id=f"{campo}-nulo") for campo in RESERVADOS
] + [
    pytest.param({k: RESERVADOS[k] for k in ("convenio_origen_id", "numero_renovacion")}, id="renovacion"),
    pytest.param({k: RESERVADOS[k] for k in ("fecha_firma", "porcentaje_avance")}, id="firma-avance"),
    pytest.param(RESERVADOS, id="todos"),
]


def _conteos(db):
    return {
        modelo.__tablename__: db.scalar(select(func.count()).select_from(modelo))
        for modelo in (Convenio, VersionConvenio, HistorialEtapa, Auditoria, SolicitudConvenio)
    }


@pytest.mark.parametrize("rol", [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI])
@pytest.mark.parametrize("campos", CASOS_RESERVADOS)
def test_creacion_rechaza_campos_reservados_sin_crear_registros(
    client, db, crear_usuario, entrar_como, rol, campos,
):
    entrar_como(crear_usuario(rol))
    original = _crear(client, objeto="Convenio que no es elegible para renovar")
    assert original.status_code == 201, original.text
    datos = dict(campos)
    if datos.get("convenio_origen_id") is not None:
        datos["convenio_origen_id"] = original.json()["id"]
    antes = _conteos(db)
    respuesta = _crear(client, objeto="Intento de asignación de campos reservados", **datos)
    assert respuesta.status_code == 422, respuesta.text
    errores = respuesta.json()["detail"]
    assert {tuple(e["loc"]) for e in errores} == {("body", campo) for campo in datos}
    assert all(e["type"] == "extra_forbidden" for e in errores)
    assert _conteos(db) == antes


@pytest.mark.parametrize("metodo,sufijo", [
    ("PATCH", ""), ("PATCH", "/elaboracion"), ("POST", "/elaboracion/finalizar"),
])
@pytest.mark.parametrize("campos", [
    pytest.param({k: v}, id=k) for k, v in RESERVADOS.items()
] + [pytest.param(RESERVADOS, id="todos")])
def test_actualizacion_y_elaboracion_ya_rechazan_campos_reservados(
    client, db, gestor, metodo, sufijo, campos,
):
    creada = _crear(client, objeto="Objeto original")
    assert creada.status_code == 201, creada.text
    convenio_id = creada.json()["id"]
    datos = dict(campos)
    if "convenio_origen_id" in datos:
        datos["convenio_origen_id"] = convenio_id
    if sufijo:
        datos.update(expected_revision=0, contenido={"type": "doc", "content": [{"type": "paragraph"}]})
    datos["objeto"] = "No debe guardarse"
    antes = _conteos(db)
    respuesta = client.request(metodo, f"/api/convenios/{convenio_id}{sufijo}", json=datos)
    assert respuesta.status_code == 422, respuesta.text
    assert {tuple(e["loc"]) for e in respuesta.json()["detail"]} == {("body", campo) for campo in campos}
    assert all(e["type"] == "extra_forbidden" for e in respuesta.json()["detail"])
    assert _conteos(db) == antes
    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    assert convenio.objeto == "Objeto original"
    assert convenio.version_actual == 1
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert all(getattr(convenio, campo) is None for campo in RESERVADOS)


def test_contrato_http_manual_no_expone_campos_reservados(client):
    respuesta = client.get("/openapi.json")
    assert respuesta.status_code == 200
    openapi = respuesta.json()
    referencia = openapi["paths"]["/api/convenios/manual"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    esquema = openapi["components"]["schemas"][referencia.rsplit("/", 1)[-1]]
    assert esquema["additionalProperties"] is False
    assert not set(RESERVADOS) & set(esquema["properties"])


@pytest.mark.parametrize("rol", [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI])
def test_creacion_sin_solicitud_con_origen_responsable_y_trazabilidad(
    client, db, crear_usuario, entrar_como, rol,
):
    gestor = crear_usuario(rol)
    entrar_como(gestor)
    respuesta = _crear(client, objeto="Acuerdo de investigación")
    assert respuesta.status_code == 201, respuesta.text
    creado = respuesta.json()
    assert creado["solicitud_id"] is None
    assert creado["origen"] == "MANUAL_ORI"
    assert creado["aliado_id"] is None
    assert creado["creado_por_id"] == gestor.id
    assert creado["creado_en"]
    assert creado["version_actual"] == 1
    assert all(creado[campo] is None for campo in RESERVADOS)
    convenio = db.get(Convenio, creado["id"])
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert convenio.solicitud is None
    elaboracion = client.get(f"/api/convenios/{creado['id']}/elaboracion")
    assert elaboracion.status_code == 200, elaboracion.text
    assert elaboracion.json()["solicitud"] is None
    assert elaboracion.json()["contenido"] == {"type": "doc", "content": [{"type": "paragraph"}]}
    historial = client.get(f"/api/convenios/{creado['id']}/revisiones")
    assert historial.status_code == 200, historial.text
    assert historial.json()["cambios_etapa"][0]["usuario"]["id"] == gestor.id
    assert "directa" in historial.json()["cambios_etapa"][0]["observacion"]


def test_no_admite_solicitud_ficticia_ni_aliado_inexistente(client, db, gestor):
    antes = db.scalar(select(Convenio.id).order_by(Convenio.id.desc()).limit(1))
    assert _crear(client, solicitud_id=999999).status_code == 422
    assert _crear(client, aliado_id=999999).status_code == 422
    despues = db.scalar(select(Convenio.id).order_by(Convenio.id.desc()).limit(1))
    assert antes == despues


@pytest.mark.parametrize("rol", [
    r for r in CodigoRol if r not in {CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI}
])
def test_roles_no_autorizados_no_pueden_crear_registros(
    client, db, crear_usuario, entrar_como, rol,
):
    tipo = TipoUsuario.EXTERNO if rol == CodigoRol.SOLICITANTE_EXTERNO else TipoUsuario.INTERNO
    entrar_como(crear_usuario(rol, tipo))
    antes = _conteos(db)
    assert _crear(client, objeto="Sin acceso").status_code == 403
    assert _conteos(db) == antes


def test_creacion_manual_requiere_sesion_sin_crear_registros(client, db):
    antes = _conteos(db)
    assert _crear(client, objeto="Sin sesión").status_code == 401
    assert _conteos(db) == antes


def test_administrador_ori_autorizado(client, db, crear_usuario, entrar_como):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    entrar_como(admin)
    respuesta = _crear(client)
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["creado_por_id"] == admin.id


def test_guardado_versiones_y_finalizacion_mantiene_doble_revision(
    client, db, gestor,
):
    creado = _crear(client).json()
    id_convenio = creado["id"]
    ruta = f"/api/convenios/{id_convenio}/elaboracion"
    original = client.get(ruta).json()
    contenido = deepcopy(original["contenido"])
    contenido["content"].append({
        "type": "paragraph",
        "content": [{"type": "text", "text": "Documento jurídico redactado desde ORI."}],
    })
    tipo_convenio_id = db.scalar(select(TipoConvenio.id).limit(1))
    assert tipo_convenio_id is not None
    payload = {
        "expected_revision": 0,
        "contenido": contenido,
        "objeto": "Cooperación académica",
        "tipo_convenio_id": tipo_convenio_id,
        "alcance": "INSTITUCIONAL",
        "implicacion_financiera": "Sin erogación",
        "duracion_meses": 12,
    }
    guardado = client.patch(ruta, json=payload)
    assert guardado.status_code == 200, guardado.text
    assert guardado.json()["version_actual"] == 1
    assert guardado.json()["revision_borrador"] == 1
    assert guardado.json()["etapa_actual"]["codigo"] == "ELABORACION"
    assert client.get(ruta).json()["contenido"] == contenido
    repetir = client.patch(ruta, json={"contenido": contenido, "expected_revision": 1})
    assert repetir.status_code == 200
    assert repetir.json()["revision_borrador"] == 1
    conflicto = client.patch(ruta, json={"contenido": contenido, "expected_revision": 0})
    assert conflicto.status_code == 409

    versiones = client.get(f"/api/convenios/{id_convenio}/versiones")
    assert versiones.status_code == 200
    assert [v["numero"] for v in versiones.json()] == [1]

    final = client.post(
        f"{ruta}/finalizar",
        json={"expected_revision": 1, "contenido": contenido},
    )
    assert final.status_code == 200, final.text
    assert db.get(Convenio, id_convenio).etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    revisiones = db.scalars(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == id_convenio,
        RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
    )).all()
    assert len(revisiones) == 1
    assert revisiones[0].instancia_juridica == 1
    assert revisiones[0].version_convenio_id is not None
    numero = final.json()["version_actual"]
    version = db.scalar(select(VersionConvenio).where(
        VersionConvenio.convenio_id == id_convenio,
        VersionConvenio.numero == numero,
    ))
    assert numero == 2
    assert version.contexto == ContextoVersionConvenio.FINALIZACION.value
    assert version.autor_id == gestor.id


def test_creacion_manual_no_modifica_flujo_original(client, gestor, crear_convenio):
    solicitado = crear_convenio(gestor)
    consulta = client.get(f"/api/convenios/{solicitado.id}")
    assert consulta.status_code == 200
    assert consulta.json()["origen"] == "SOLICITUD"
    assert consulta.json()["solicitud_id"] is not None


def test_aliado_opcional_hasta_envio_contraparte(client, db, gestor):
    """HU-10 CA-02/07: sin aliado se puede elaborar; se exigirá al enviar a contraparte."""
    creado = _crear(client).json()
    tipo_id = db.scalar(select(TipoConvenio.id).limit(1))
    ruta = f"/api/convenios/{creado['id']}/elaboracion"
    guardar = client.patch(ruta, json={
        "expected_revision": 0,
        "contenido": {"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "Acuerdo institucional redactado por la ORI"}
        ]}]},
        "objeto": "Convenio manual sin aliado asignado todavía",
        "tipo_convenio_id": tipo_id,
        "alcance": "INSTITUCIONAL",
        "implicacion_financiera": "Sin compromiso financiero",
        "duracion_meses": 12,
    })
    assert guardar.status_code == 200, guardar.text
    final = client.post(f"{ruta}/finalizar", json={
        "expected_revision": guardar.json()["revision_borrador"],
        "contenido": guardar.json()["contenido"],
    })
    assert final.status_code == 200, final.text
    db.expire_all()
    convenio = db.get(Convenio, creado["id"])
    assert convenio is not None
    assert convenio.etapa_actual is not None
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    assert final.json()["etapa_actual_id"] == convenio.etapa_actual_id
    convenio = db.get(Convenio, creado["id"])
    assert convenio is not None
    assert final.json()["etapa_actual_id"] == convenio.etapa_actual_id
    assert convenio.etapa_actual is not None
    assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"


@pytest.mark.parametrize("retirar", [False, True], ids=["cambiar", "retirar"])
def test_patch_sincroniza_aliado_en_respuesta_y_persistencia(client, db, gestor, retirar):
    aliados = [Aliado(
        nombre=f"Universidad de prueba {numero}", tipo="UNIVERSIDAD",
        tipo_identificacion="NIT", identificacion=f"HU10-PATCH-{gestor.id}-{numero}",
        ciudad="Bogotá",
    ) for numero in (1, 2)]
    db.add_all(aliados)
    db.flush()
    original_id, nuevo_id = [aliado.id for aliado in aliados]
    creado = _crear(client, objeto="Convenio para actualizar aliado", aliado_id=original_id)
    assert creado.status_code == 201, creado.text
    convenio_id = creado.json()["id"]
    assert creado.json()["aliado"]["id"] == original_id
    esperado = None if retirar else nuevo_id

    respuesta = client.patch(f"/api/convenios/{convenio_id}", json={"aliado_id": esperado})

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert datos["aliado_id"] == esperado
    if retirar:
        assert datos["aliado"] is None
    else:
        assert datos["aliado"]["id"] == datos["aliado_id"]
    db.expire_all()
    persistido = db.get(Convenio, convenio_id)
    assert persistido.aliado_id == esperado
    assert (persistido.aliado.id if persistido.aliado else None) == esperado

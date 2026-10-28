from datetime import datetime

import pytest
import test_hu10_exportacion as hu10
import test_hu15_revision_final_firmas as hu15
from sqlalchemy import func, select

from backend.core.roles import CodigoRol
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.solicitud_convenio import SolicitudConvenio

manual_documentado = hu10.manual_documentado
escenario_final = hu15.escenario_final


@pytest.fixture
def convenio_listo(manual_documentado):
    return manual_documentado


def test_manual_registra_inicio_y_activacion_pendiente_sin_solicitud_ficticia(
    client, db, gestor
):
    solicitudes_antes = db.scalar(select(func.count()).select_from(SolicitudConvenio))
    creada = client.post("/api/convenios/manual", json={"objeto": "Acuerdo manual"})
    assert creada.status_code == 201, creada.text
    convenio = db.get(Convenio, creada.json()["id"])
    assert convenio.solicitud_id is None
    ingreso = db.scalar(select(HistorialEtapa).where(
        HistorialEtapa.convenio_id == convenio.id, HistorialEtapa.etapa_origen_id.is_(None)
    ))
    assert convenio.elaboracion_iniciada_en == ingreso.fecha_cambio
    assert convenio.elaboracion_iniciada_en is not None
    linea = client.get(f"/api/convenios/{convenio.id}/linea-tiempo")
    assert linea.status_code == 200, linea.text
    inicio, activacion = linea.json()
    assert inicio["codigo"] == "INICIO_ELABORACION"
    assert datetime.fromisoformat(inicio["fecha"]) == convenio.elaboracion_iniciada_en
    assert activacion == {
        "codigo": "ACTIVACION", "nombre": "Activación", "estado": "PENDIENTE", "fecha": None
    }
    (registro,) = db.scalars(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id
    )).all()
    assert (registro.accion, registro.usuario_id, registro.rol, registro.contexto) == (
        "INSERT", gestor.id, CodigoRol.GESTOR_ORI.value, "Creó el convenio manualmente"
    )
    assert db.scalar(select(func.count()).select_from(SolicitudConvenio)) == solicitudes_antes


@pytest.mark.parametrize("campo", ["elaboracion_iniciada_en", "activado_en"])
@pytest.mark.parametrize("metodo,sufijo", [
    ("POST", "/manual"), ("PATCH", ""),
    ("PATCH", "/elaboracion"), ("POST", "/elaboracion/finalizar"),
])
def test_cliente_no_fija_hitos_manuales(client, db, gestor, campo, metodo, sufijo):
    creada = client.post("/api/convenios/manual", json={})
    assert creada.status_code == 201
    identificador = creada.json()["id"]
    convenio = db.get(Convenio, identificador)
    inicio = convenio.elaboracion_iniciada_en
    datos = {campo: "2020-01-01T00:00:00Z"}
    if "elaboracion" in sufijo:
        datos.update(expected_revision=0, contenido={"type": "doc", "content": [{"type": "paragraph"}]})
    ruta = "/api/convenios/manual" if sufijo == "/manual" else f"/api/convenios/{identificador}{sufijo}"
    respuesta = client.request(metodo, ruta, json=datos)
    assert respuesta.status_code == 422, respuesta.text
    assert {tuple(e["loc"]) for e in respuesta.json()["detail"]} == {("body", campo)}
    db.refresh(convenio)
    assert convenio.elaboracion_iniciada_en == inicio
    assert convenio.activado_en is None


def test_formalizar_manual_registra_activacion_y_auditoria_sin_crear_solicitud(
    client, db, escenario_final
):
    convenio = escenario_final["convenio"]
    assert convenio.solicitud_id is None
    assert convenio.activado_en is None
    solicitudes_antes = db.scalar(select(func.count()).select_from(SolicitudConvenio))
    proceso = hu15._iniciar_proceso(client, escenario_final, ["FISICA"] * 7)
    firmas = hu15._registrar_fisicas(client, convenio.id, [f["id"] for f in proceso["firmas"]])
    assert firmas.status_code == 201, firmas.text

    respuesta = client.post(f"/api/convenios/{convenio.id}/firmas/formalizar")
    assert respuesta.status_code == 200, respuesta.text
    db.refresh(convenio)
    proceso_persistido = db.get(ProcesoFirmasConvenio, proceso["id"])
    assert convenio.activado_en == proceso_persistido.completado_en
    assert convenio.activado_en is not None
    linea = client.get(f"/api/convenios/{convenio.id}/linea-tiempo").json()
    assert [h["codigo"] for h in linea] == ["INICIO_ELABORACION", "ACTIVACION", "VENCIMIENTO"]
    assert linea[1]["estado"] == "COMPLETADO"
    assert datetime.fromisoformat(linea[1]["fecha"]) == convenio.activado_en
    (registro,) = db.scalars(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id,
        Auditoria.campo == "activado_en",
    )).all()
    assert (registro.usuario_id, registro.rol, registro.accion) == (
        escenario_final["gestor"].id, CodigoRol.GESTOR_ORI.value, "UPDATE"
    )
    assert datetime.fromisoformat(registro.valor_nuevo) == convenio.activado_en
    assert convenio.solicitud_id is None
    assert db.scalar(select(func.count()).select_from(SolicitudConvenio)) == solicitudes_antes

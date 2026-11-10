from copy import deepcopy
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.enums import ContextoVersionConvenio, EstadoConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrearManual
from backend.services import renovaciones
from backend.services.convenios import ServicioConvenios
from backend.services.pdf_convenio import ServicioPdfConvenio
from backend.services.renovaciones import ServicioRenovaciones

DOCUMENTO_VACIO = {"type": "doc", "content": [{"type": "paragraph"}]}
DOCUMENTO_ELABORADO = {
    "type": "doc",
    "content": [
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Cláusula elaborada por la ORI"}],
        }
    ],
}
DATOS_COMPLETOS = {
    "objeto": "Cooperación académica",
    "alcance": "INSTITUCIONAL",
    "implicacion_financiera": "Sin costo para la Universidad",
    "duracion_meses": 24,
}


def _ruta(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/elaboracion"


def _versiones(db, convenio_id: int) -> list[VersionConvenio]:
    db.expire_all()
    return list(
        db.scalars(
            select(VersionConvenio)
            .where(VersionConvenio.convenio_id == convenio_id)
            .order_by(VersionConvenio.numero)
        )
    )


def _borrador(db, convenio_id: int) -> BorradorConvenio | None:
    return db.scalar(
        select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio_id)
    )


def _revision_pendiente(db, convenio_id: int) -> RevisionConvenio:
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


@pytest.fixture
def convenio_manual(client, db, gestor, tipo_marco) -> Convenio:
    respuesta = client.post(
        "/api/convenios/manual",
        json={**DATOS_COMPLETOS, "tipo_convenio_id": tipo_marco},
    )
    assert respuesta.status_code == 201, respuesta.text
    return db.get(Convenio, respuesta.json()["id"])


@pytest.fixture
def tipo_marco(db) -> int:
    return db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO"))


# ---- CA-02 y RN-01: un convenio nuevo nace sin versión formal -------------------


def test_convenio_manual_nace_sin_version_y_con_documento_vacio_como_borrador(
    client, db, gestor, convenio_manual
) -> None:
    assert convenio_manual.version_actual == 0
    assert _versiones(db, convenio_manual.id) == []
    borrador = _borrador(db, convenio_manual.id)
    assert borrador.contenido == DOCUMENTO_VACIO
    assert borrador.revision == 1
    assert borrador.actualizado_por_id == gestor.id

    cuerpo = client.get(_ruta(convenio_manual.id)).json()
    assert cuerpo["version_actual"] == 0
    assert cuerpo["contenido"] == DOCUMENTO_VACIO
    assert cuerpo["revision_borrador"] == 1
    assert client.get(f"/api/convenios/{convenio_manual.id}/versiones").json() == []


def test_convenio_desde_solicitud_nace_sin_version_y_con_la_plantilla_como_borrador(
    client, db, gestor, convenio_listo
) -> None:
    assert convenio_listo.version_actual == 0
    assert _versiones(db, convenio_listo.id) == []
    borrador = _borrador(db, convenio_listo.id)
    assert "Objeto solicitado originalmente" in str(borrador.contenido)
    assert client.get(_ruta(convenio_listo.id)).json()["contenido"] == borrador.contenido


@pytest.mark.parametrize("manual", [True, False], ids=["manual", "solicitud"])
def test_renovacion_nace_sin_version_y_con_la_copia_del_origen_como_borrador(
    db, gestor, crear_convenio, formalizar_version, monkeypatch, manual
) -> None:
    monkeypatch.setattr(renovaciones, "fecha_actual_dominio", lambda: date(2026, 1, 1))
    if manual:
        origen = ServicioConvenios(db).crear_manual(
            ConvenioCrearManual(objeto="Convenio de origen"), gestor
        )
    else:
        origen = crear_convenio(gestor)
    _borrador(db, origen.id).contenido = deepcopy(DOCUMENTO_ELABORADO)
    db.commit()
    version_origen = formalizar_version(origen, gestor)
    origen.estado = EstadoConvenio.FINALIZADO.value
    origen.fecha_vencimiento = date(2025, 12, 31)
    db.commit()

    hijo = ServicioRenovaciones(db).iniciar_renovacion(origen.id, gestor)

    assert hijo.version_actual == 0
    assert _versiones(db, hijo.id) == []
    borrador = _borrador(db, hijo.id)
    assert borrador.contenido == DOCUMENTO_ELABORADO
    assert borrador.contenido is not version_origen.contenido
    assert [version.numero for version in _versiones(db, origen.id)] == [1]


# ---- RN-03: el primer envío a revisión genera la V1 -----------------------------


def test_el_primer_envio_del_convenio_manual_genera_la_v1_con_lo_elaborado(
    client, db, gestor, convenio_manual
) -> None:
    guardado = client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 1},
    )
    assert guardado.status_code == 200, guardado.text
    assert guardado.json()["version_actual"] == 0
    assert guardado.json()["revision_borrador"] == 2
    assert _versiones(db, convenio_manual.id) == []

    enviado = client.post(
        f"{_ruta(convenio_manual.id)}/finalizar",
        json={"expected_revision": 2},
    )

    assert enviado.status_code == 200, enviado.text
    assert enviado.json()["version_actual"] == 1
    (v1,) = _versiones(db, convenio_manual.id)
    assert v1.numero == 1
    assert v1.contenido == DOCUMENTO_ELABORADO
    assert v1.contexto == ContextoVersionConvenio.FINALIZACION.value
    assert v1.autor_id == gestor.id
    assert v1.snapshot_metadata["origen"] == "MANUAL_ORI"
    assert v1.snapshot_metadata["objeto"] == DATOS_COMPLETOS["objeto"]
    assert v1.etapa.codigo == "ELABORACION"
    assert _revision_pendiente(db, convenio_manual.id).version_convenio_id == v1.id
    assert _borrador(db, convenio_manual.id) is None


def test_el_primer_envio_sin_editar_la_plantilla_tambien_genera_la_v1(
    client, db, gestor, convenio_listo
) -> None:
    plantilla = deepcopy(_borrador(db, convenio_listo.id).contenido)

    enviado = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert enviado.status_code == 200, enviado.text
    (v1,) = _versiones(db, convenio_listo.id)
    assert v1.numero == 1
    assert v1.contenido == plantilla
    assert v1.snapshot_metadata["origen"] == "SOLICITUD"
    assert v1.snapshot_metadata["convenio_origen_id"] is None
    assert v1.snapshot_metadata["numero_renovacion"] is None


def test_un_documento_vacio_no_se_puede_enviar_y_no_crea_version(
    client, db, convenio_manual
) -> None:
    respuesta = client.post(f"{_ruta(convenio_manual.id)}/finalizar")

    assert respuesta.status_code == 422, respuesta.text
    assert {item["campo"] for item in respuesta.json()["detail"]["faltantes"]} == {
        "contenido"
    }
    db.expire_all()
    convenio = db.get(Convenio, convenio_manual.id)
    assert convenio.version_actual == 0
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert _versiones(db, convenio.id) == []
    assert _borrador(db, convenio.id).contenido == DOCUMENTO_VACIO
    assert db.scalar(
        select(func.count())
        .select_from(RevisionConvenio)
        .where(RevisionConvenio.convenio_id == convenio.id)
    ) == 0


def test_la_validacion_de_elaboracion_revisa_el_borrador_sin_version_formal(
    client, convenio_manual
) -> None:
    faltantes = client.get(f"{_ruta(convenio_manual.id)}/validacion").json()["faltantes"]
    assert "contenido" in {item["campo"] for item in faltantes}

    client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 1},
    )

    faltantes = client.get(f"{_ruta(convenio_manual.id)}/validacion").json()["faltantes"]
    assert "contenido" not in {item["campo"] for item in faltantes}


def test_los_ciclos_siguientes_continuan_la_numeracion_desde_la_v1(
    client, db, gestor, revisor, convenio_manual
) -> None:
    client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 1},
    )
    assert client.post(f"{_ruta(convenio_manual.id)}/finalizar").status_code == 200
    servicio = ServicioConvenios(db)
    devuelta = servicio.devolver(
        convenio_manual.id,
        _revision_pendiente(db, convenio_manual.id).id,
        ["Precisar el objeto"],
        1,
        revisor,
    )
    servicio.atender_observacion(
        convenio_manual.id, devuelta.observaciones[0].id, "Objeto precisado", gestor
    )
    elaboracion = client.get(_ruta(convenio_manual.id)).json()
    assert elaboracion["version_actual"] == 1
    assert elaboracion["revision_borrador"] == 0
    assert elaboracion["contenido"] == DOCUMENTO_ELABORADO
    corregido = deepcopy(DOCUMENTO_ELABORADO)
    corregido["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": "Corrección"}]}
    )
    assert client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": corregido, "expected_revision": 0},
    ).status_code == 200

    assert client.post(f"{_ruta(convenio_manual.id)}/finalizar").status_code == 200

    versiones = _versiones(db, convenio_manual.id)
    assert [version.numero for version in versiones] == [1, 2]
    assert versiones[0].contenido == DOCUMENTO_ELABORADO
    assert versiones[1].contenido == corregido


# ---- Compatibilidad: los convenios existentes conservan su numeración -----------


def test_un_convenio_con_v1_previa_conserva_su_numeracion_y_sigue_en_v2(
    client, db, gestor, convenio_manual, formalizar_version
) -> None:
    formalizar_version(
        convenio_manual, gestor, ContextoVersionConvenio.INICIALIZACION
    )
    v1_antes = deepcopy(_versiones(db, convenio_manual.id)[0].contenido)
    elaboracion = client.get(_ruta(convenio_manual.id)).json()
    assert elaboracion["version_actual"] == 1
    assert elaboracion["revision_borrador"] == 0
    assert client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 0},
    ).status_code == 200

    enviado = client.post(f"{_ruta(convenio_manual.id)}/finalizar")

    assert enviado.status_code == 200, enviado.text
    assert enviado.json()["version_actual"] == 2
    versiones = _versiones(db, convenio_manual.id)
    assert [version.numero for version in versiones] == [1, 2]
    assert versiones[0].contenido == v1_antes
    assert versiones[0].contexto == ContextoVersionConvenio.INICIALIZACION.value
    assert versiones[1].contenido == DOCUMENTO_ELABORADO


# ---- RN-05: sin versión formal no se muestra un número --------------------------


def test_los_documentos_de_trabajo_indican_que_no_hay_version_formal(
    client, db, convenio_manual
) -> None:
    client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 1},
    )
    aliado = Aliado(
        nombre="Universidad aliada",
        tipo="UNIVERSIDAD",
        tipo_identificacion="NIT",
        identificacion="900123456",
        ciudad="Cali",
    )
    db.get(Convenio, convenio_manual.id).aliado = aliado
    db.commit()

    excel = client.get(
        f"/api/convenios/{convenio_manual.id}/exportar", params={"formato": "excel"}
    )

    assert excel.status_code == 200, excel.text
    generales = {
        fila[0]: fila[1]
        for fila in load_workbook(BytesIO(excel.content))["Datos Generales"].values
        if fila[0]
    }
    assert generales["Versión del documento"] == "Sin versión formal"
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_manual.id, db)
    assert dto.version_actual == 0
    assert ServicioPdfConvenio().renderizar_dto_a_pdf(dto).startswith(b"%PDF-")


# ---- Bitácora: sin versión formal no se declara un número ----------------------


def test_la_bitacora_no_declara_version_mientras_no_exista_una_formal(
    client, db, gestor, convenio_manual
) -> None:
    client.patch(
        _ruta(convenio_manual.id),
        json={"contenido": DOCUMENTO_ELABORADO, "expected_revision": 1},
    )
    client.post(f"{_ruta(convenio_manual.id)}/finalizar")

    db.expire_all()
    filas = list(
        db.scalars(
            select(Auditoria).where(Auditoria.usuario_id == gestor.id).order_by(Auditoria.id)
        )
    )
    por_evento = {fila.evento: fila for fila in filas if fila.evento}
    assert por_evento["CONVENIO_CREADO_MANUAL"].version is None
    assert por_evento["BORRADOR_GUARDADO"].version is None
    assert por_evento["VERSION_GENERADA"].version == 1


# ---- Atomicidad: un error al crear no deja convenio ni borrador -----------------


def test_un_error_al_crear_el_borrador_no_deja_el_convenio(
    db, gestor, monkeypatch
) -> None:
    total = select(func.count()).select_from(Convenio)
    antes = db.scalar(total), db.scalar(select(func.count()).select_from(BorradorConvenio))

    def fallar(*_args, **_kwargs):
        raise SQLAlchemyError("Fallo al crear el borrador")

    monkeypatch.setattr(ServicioConvenios, "_crear_borrador_inicial", fallar)

    with pytest.raises(SQLAlchemyError, match="Fallo al crear el borrador"):
        ServicioConvenios(db).crear_manual(ConvenioCrearManual(), gestor)

    assert (
        db.scalar(total),
        db.scalar(select(func.count()).select_from(BorradorConvenio)),
    ) == antes

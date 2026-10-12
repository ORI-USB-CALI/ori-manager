from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.documento import Documento
from backend.models.solicitud_version import SolicitudVersion
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.schemas.solicitud import SolicitudCampos
from backend.services.documentos import AlmacenDocumentosLocal

TIPO_SOPORTE = "OTRO_DOCUMENTO_REPRESENTACION"


def _payload(tipo_convenio_id: int) -> dict[str, object]:
    texto = {
        campo: f"Valor de {campo}"
        for campo in SolicitudCampos.model_fields
        if campo not in {"tipo_convenio_id", "solicitante_nombre", "solicitante_correo",
                         "solicitante_documento", "solicitante_entidad"}
    }
    return {
        **texto,
        "tipo_identificacion_aliado_propuesto": "NIT",
        "identificacion_aliado_propuesto": "900123456",
        "tipo_aliado_propuesto": "EMPRESA",
        "correo_aliado_propuesto": "contacto@contraparte.com",
        "contacto_contraparte_correo": "persona@example.com",
        "supervisor_usb_correo": "supervisor.usb@example.com",
        "supervisor_contraparte_correo": "supervisor.contraparte@example.com",
        "objeto": "Objeto del convenio",
        "vigencia_estimada": "24 meses",
        "tipo_convenio_id": tipo_convenio_id,
    }


@pytest.fixture
def unidad(db) -> UnidadOrganizacional:
    item = UnidadOrganizacional(
        codigo=f"U-{uuid4().hex[:8]}",
        nombre="Facultad de prueba",
        tipo=TipoUnidad.FACULTAD.value,
    )
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def tipo_convenio(db) -> TipoConvenio:
    return db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))


@pytest.fixture
def solicitante(crear_usuario, entrar_como, db, unidad):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, tipo_usuario=TipoUsuario.INTERNO)
    usuario.unidad_organizacional_id = unidad.id
    usuario.cargo = "Coordinadora"
    db.commit()
    entrar_como(usuario)
    return usuario


@pytest.fixture
def gestor_ori(crear_usuario):
    return crear_usuario(CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO)


@pytest.fixture
def almacen(tmp_path) -> AlmacenDocumentosLocal:
    return AlmacenDocumentosLocal(tmp_path / "documentos")


def _subir(client, solicitud_id: int, contenido: bytes = b"%PDF-1.4 soporte") -> int:
    respuesta = client.post(
        f"/api/solicitudes/{solicitud_id}/documentos",
        data={"tipo_documento": TIPO_SOPORTE},
        files={"archivo": ("soporte.pdf", BytesIO(contenido), "application/pdf")},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def _crear_y_radicar(client, tipo_convenio) -> tuple[int, int]:
    creada = client.post("/api/solicitudes", json=_payload(tipo_convenio.id))
    assert creada.status_code == 201, creada.text
    solicitud_id = creada.json()["id"]
    documento_id = _subir(client, solicitud_id)
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200
    return solicitud_id, documento_id


def _devolver(client, entrar_como, gestor, solicitante, solicitud_id: int) -> None:
    entrar_como(gestor)
    respuesta = client.post(
        f"/api/solicitudes/recibidas/{solicitud_id}/devolver",
        json={"observaciones": "Ajustar la vigencia y el soporte"},
    )
    assert respuesta.status_code == 200, respuesta.text
    entrar_como(solicitante)


def _versiones(db, solicitud_id: int) -> list[SolicitudVersion]:
    db.expire_all()
    return list(
        db.scalars(
            select(SolicitudVersion)
            .where(SolicitudVersion.solicitud_id == solicitud_id)
            .order_by(SolicitudVersion.numero)
        )
    )


# ---- Migración ---------------------------------------------------------------


def test_migracion_crea_las_tablas_de_versiones(db) -> None:
    inspector = inspect(db.connection())

    columnas = {c["name"] for c in inspector.get_columns("solicitud_version")}
    assert {
        "id", "solicitud_id", "numero", "datos", "radicada_por_id", "radicada_en",
    } <= columnas
    unicos = inspector.get_unique_constraints("solicitud_version")
    assert any(set(u["column_names"]) == {"solicitud_id", "numero"} for u in unicos)
    assert {
        c["name"] for c in inspector.get_columns("solicitud_version_documento")
    } == {"solicitud_version_id", "documento_id"}


# ---- CA-01: la radicación y la re-radicación generan versiones ---------------


def test_radicar_guarda_la_version_1_con_formulario_y_documentos(
    db, client, solicitante, tipo_convenio
) -> None:
    solicitud_id, documento_id = _crear_y_radicar(client, tipo_convenio)

    [version] = _versiones(db, solicitud_id)
    detalle = client.get(f"/api/solicitudes/{solicitud_id}").json()

    assert version.numero == 1
    assert version.radicada_por_id == solicitante.id
    assert version.radicada_en.isoformat().replace("+00:00", "Z")[:19] == (
        detalle["fecha_radicacion"][:19]
    )
    assert set(version.datos) == set(SolicitudCampos.model_fields)
    assert version.datos["objeto"] == "Objeto del convenio"
    assert version.datos["tipo_convenio_id"] == tipo_convenio.id
    assert [d.id for d in version.documentos] == [documento_id]


def test_re_radicar_tras_devolucion_crea_una_nueva_version_de_la_misma_solicitud(
    db, client, entrar_como, solicitante, gestor_ori, tipo_convenio
) -> None:
    solicitud_id, _ = _crear_y_radicar(client, tipo_convenio)
    _devolver(client, entrar_como, gestor_ori, solicitante, solicitud_id)

    assert client.patch(
        f"/api/solicitudes/{solicitud_id}", json={"vigencia_estimada": "36 meses"}
    ).status_code == 200
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    versiones = _versiones(db, solicitud_id)
    assert [v.numero for v in versiones] == [1, 2]
    assert {v.solicitud_id for v in versiones} == {solicitud_id}
    assert versiones[1].datos["vigencia_estimada"] == "36 meses"


def test_radicacion_incompleta_no_crea_version(
    db, client, solicitante, tipo_convenio
) -> None:
    creada = client.post("/api/solicitudes", json=_payload(tipo_convenio.id))
    solicitud_id = creada.json()["id"]

    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 422
    assert _versiones(db, solicitud_id) == []


def test_numero_de_version_es_unico_por_solicitud(
    db, client, solicitante, tipo_convenio
) -> None:
    solicitud_id, _ = _crear_y_radicar(client, tipo_convenio)
    [version] = _versiones(db, solicitud_id)

    db.add(
        SolicitudVersion(
            solicitud_id=solicitud_id,
            numero=1,
            datos={},
            radicada_por_id=solicitante.id,
            radicada_en=version.radicada_en,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ---- CA-04: la versión anterior no se sobrescribe ni se pierde ---------------


def test_corregir_la_solicitud_no_altera_la_version_anterior(
    db, client, entrar_como, solicitante, gestor_ori, tipo_convenio
) -> None:
    solicitud_id, documento_id = _crear_y_radicar(client, tipo_convenio)
    _devolver(client, entrar_como, gestor_ori, solicitante, solicitud_id)

    client.patch(
        f"/api/solicitudes/{solicitud_id}",
        json={"objeto": "Objeto corregido", "vigencia_estimada": "36 meses"},
    )
    client.post(f"/api/solicitudes/{solicitud_id}/radicar")

    primera, segunda = _versiones(db, solicitud_id)
    assert primera.datos["objeto"] == "Objeto del convenio"
    assert primera.datos["vigencia_estimada"] == "24 meses"
    assert segunda.datos["objeto"] == "Objeto corregido"
    assert [d.id for d in primera.documentos] == [documento_id]


def test_documento_retirado_tras_devolucion_se_conserva_en_su_version(
    db, client, entrar_como, solicitante, gestor_ori, tipo_convenio, almacen
) -> None:
    solicitud_id, anterior_id = _crear_y_radicar(client, tipo_convenio)
    _devolver(client, entrar_como, gestor_ori, solicitante, solicitud_id)
    nuevo_id = _subir(client, solicitud_id, b"%PDF-1.4 soporte corregido")

    eliminado = client.delete(f"/api/solicitudes/{solicitud_id}/documentos/{anterior_id}")
    assert eliminado.status_code == 204
    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 200

    primera, segunda = _versiones(db, solicitud_id)
    anterior = db.get(Documento, anterior_id)
    assert anterior is not None
    assert anterior.es_vigente is False
    assert almacen.leer(anterior.ruta_almacenamiento) == b"%PDF-1.4 soporte"
    assert [d.id for d in primera.documentos] == [anterior_id]
    assert [d.id for d in segunda.documentos] == [nuevo_id]


def test_documento_retirado_deja_de_figurar_en_la_solicitud(
    client, entrar_como, solicitante, gestor_ori, tipo_convenio
) -> None:
    solicitud_id, anterior_id = _crear_y_radicar(client, tipo_convenio)
    _devolver(client, entrar_como, gestor_ori, solicitante, solicitud_id)
    nuevo_id = _subir(client, solicitud_id)

    client.delete(f"/api/solicitudes/{solicitud_id}/documentos/{anterior_id}")

    documentos = client.get(f"/api/solicitudes/{solicitud_id}").json()["documentos"]
    assert [d["id"] for d in documentos] == [nuevo_id]
    assert client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{anterior_id}"
    ).status_code == 404


def test_sin_documento_vigente_no_se_puede_re_radicar(
    db, client, entrar_como, solicitante, gestor_ori, tipo_convenio
) -> None:
    solicitud_id, anterior_id = _crear_y_radicar(client, tipo_convenio)
    _devolver(client, entrar_como, gestor_ori, solicitante, solicitud_id)

    client.delete(f"/api/solicitudes/{solicitud_id}/documentos/{anterior_id}")

    assert client.post(f"/api/solicitudes/{solicitud_id}/radicar").status_code == 422
    assert len(_versiones(db, solicitud_id)) == 1


def test_documento_de_borrador_nunca_radicado_se_elimina_fisicamente(
    db, client, solicitante, tipo_convenio, almacen
) -> None:
    creada = client.post("/api/solicitudes", json=_payload(tipo_convenio.id))
    solicitud_id = creada.json()["id"]
    documento_id = _subir(client, solicitud_id)
    ruta = db.get(Documento, documento_id).ruta_almacenamiento

    assert client.delete(
        f"/api/solicitudes/{solicitud_id}/documentos/{documento_id}"
    ).status_code == 204

    db.expire_all()
    assert db.get(Documento, documento_id) is None
    assert not almacen.existe(ruta)

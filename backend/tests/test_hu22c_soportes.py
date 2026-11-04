"""HU-22C: listado y descarga de soportes (CA-03) y autorización (CA-04)."""
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from backend.api.routers.convenios import _lanzar_http
from backend.core.roles import CodigoRol
from backend.models.documento import Documento
from backend.models.enums import EstadoConvenio
from backend.services.documentos import AlmacenDocumentosLocal
from backend.services.soportes_convenio import (
    ConvenioNoAdmiteSoportes,
    ServicioSoportesConvenio,
)

PDF = b"%PDF-1.4\n% soporte de convenio\n"


def _agregar_documento(
    db, convenio, tmp_path, *, autor=None, tipo="SOPORTE", nombre="acta.pdf",
    es_vigente=True,
) -> Documento:
    clave = f"convenios/{convenio.id}/{uuid4().hex}.pdf"
    AlmacenDocumentosLocal(tmp_path / "documentos").guardar(clave, PDF)
    documento = Documento(
        convenio_id=convenio.id,
        tipo=tipo,
        nombre_archivo=nombre,
        ruta_almacenamiento=clave,
        tipo_mime="application/pdf",
        tamano_bytes=len(PDF),
        es_vigente=es_vigente,
        cargado_por_id=autor.id if autor else None,
    )
    db.add(documento)
    db.commit()
    return documento


def _cargar(client, convenio_id):
    return client.post(
        f"/api/convenios/{convenio_id}/documentos",
        files={"archivo": ("soporte.pdf", PDF, "application/pdf")},
    )


@pytest.fixture
def convenio(gestor, crear_convenio):
    return crear_convenio(gestor)


# ---- CA-03: listado ---------------------------------------------------------


def test_lista_solo_los_soportes_vigentes_del_convenio(
    client, db, gestor, convenio, crear_convenio, tmp_path
):
    antiguo = _agregar_documento(db, convenio, tmp_path, autor=gestor, nombre="a.pdf")
    reciente = _agregar_documento(db, convenio, tmp_path, nombre="b.pdf")
    _agregar_documento(db, convenio, tmp_path, tipo="AVAL_JURIDICO")
    _agregar_documento(db, convenio, tmp_path, es_vigente=False)
    _agregar_documento(db, crear_convenio(gestor), tmp_path)

    respuesta = client.get(f"/api/convenios/{convenio.id}/documentos")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # Del más reciente al más antiguo; no aparecen otros tipos, versiones no
    # vigentes ni soportes de otros convenios.
    assert [item["id"] for item in cuerpo] == [reciente.id, antiguo.id]
    assert set(cuerpo[1]) == {
        "id",
        "nombre_original",
        "tamano_bytes",
        "fecha_creacion",
        "usuario_nombre",
    }
    assert cuerpo[1]["nombre_original"] == "a.pdf"
    assert cuerpo[1]["tamano_bytes"] == len(PDF)
    assert datetime.fromisoformat(cuerpo[1]["fecha_creacion"]).tzinfo is not None
    assert cuerpo[1]["usuario_nombre"] == gestor.nombre_completo
    assert cuerpo[0]["usuario_nombre"] is None


def test_lista_vacia_si_el_convenio_no_tiene_soportes(client, gestor, convenio):
    respuesta = client.get(f"/api/convenios/{convenio.id}/documentos")
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_listado_de_convenio_inexistente_responde_404(client, gestor):
    assert client.get("/api/convenios/999999999/documentos").status_code == 404


# ---- CA-03: descarga --------------------------------------------------------


def test_descarga_el_soporte_como_adjunto_por_defecto(
    client, db, gestor, convenio, tmp_path
):
    soporte = _agregar_documento(db, convenio, tmp_path, nombre="acta inicio.pdf")

    respuesta = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )

    assert respuesta.status_code == 200
    assert respuesta.content == PDF
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''acta%20inicio.pdf"
    )
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["cache-control"] == "no-store"


def test_descarga_inline_para_visualizar_en_el_navegador(
    client, db, gestor, convenio, tmp_path
):
    soporte = _agregar_documento(db, convenio, tmp_path)
    ruta = f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"

    respuesta = client.get(ruta, params={"disposicion": "inline"})

    assert respuesta.status_code == 200
    assert respuesta.headers["content-disposition"].startswith("inline;")
    assert client.get(ruta, params={"disposicion": "otra"}).status_code == 422


def test_no_descarga_soportes_de_otro_convenio_ni_otros_tipos(
    client, db, gestor, convenio, crear_convenio, tmp_path
):
    ajeno = _agregar_documento(db, crear_convenio(gestor), tmp_path)
    aval = _agregar_documento(db, convenio, tmp_path, tipo="AVAL_JURIDICO")
    reemplazado = _agregar_documento(db, convenio, tmp_path, es_vigente=False)

    for documento in (ajeno, aval, reemplazado):
        respuesta = client.get(
            f"/api/convenios/{convenio.id}/documentos/{documento.id}/descargar"
        )
        assert respuesta.status_code == 404


def test_descarga_responde_502_si_el_archivo_no_esta_almacenado(
    client, db, gestor, convenio, tmp_path
):
    soporte = _agregar_documento(db, convenio, tmp_path)
    AlmacenDocumentosLocal(tmp_path / "documentos").eliminar(
        soporte.ruta_almacenamiento
    )

    respuesta = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )

    assert respuesta.status_code == 502


# ---- CA-04: autorización por rol ------------------------------------------


def test_administrador_ori_puede_listar_y_descargar(
    client, db, gestor, convenio, crear_usuario, entrar_como, tmp_path
):
    soporte = _agregar_documento(db, convenio, tmp_path)
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    assert client.get(f"/api/convenios/{convenio.id}/documentos").status_code == 200
    descarga = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )
    assert descarga.status_code == 200


@pytest.mark.parametrize(
    "rol",
    [
        CodigoRol.REVISOR_ORI,
        CodigoRol.SOLICITANTE_INTERNO,
        CodigoRol.SOLICITANTE_EXTERNO,
    ],
)
def test_otros_roles_reciben_403(
    client, db, gestor, convenio, crear_usuario, entrar_como, tmp_path, rol
):
    soporte = _agregar_documento(db, convenio, tmp_path)
    entrar_como(crear_usuario(rol))

    listado = client.get(f"/api/convenios/{convenio.id}/documentos")
    descarga = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )
    carga = _cargar(client, convenio.id)

    assert listado.status_code == 403
    assert descarga.status_code == 403
    assert carga.status_code == 403


def test_sin_sesion_responde_401(client, convenio):
    client.cookies.clear()
    assert client.get(f"/api/convenios/{convenio.id}/documentos").status_code == 401


# ---- CA-04: estado del convenio ---------------------------------------------


@pytest.mark.parametrize(
    "estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER]
)
def test_convenio_activo_admite_carga_de_soportes(db, convenio, estado):
    convenio.estado = estado.value
    db.commit()

    assert ServicioSoportesConvenio(db).verificar_carga(convenio.id) is convenio


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.EN_TRAMITE,
        EstadoConvenio.VENCIDO,
        EstadoConvenio.RENOVADO,
        EstadoConvenio.FINALIZADO,
        EstadoConvenio.CANCELADO,
    ],
)
def test_convenio_no_activo_rechaza_carga_con_422(db, convenio, estado):
    convenio.estado = estado.value
    db.commit()

    with pytest.raises(ConvenioNoAdmiteSoportes) as error:
        ServicioSoportesConvenio(db).verificar_carga(convenio.id)
    assert estado.value in str(error.value)

    # El router traduce la regla de negocio a 422 con el mensaje explicativo.
    with pytest.raises(HTTPException) as http:
        _lanzar_http(error.value)
    assert http.value.status_code == 422
    assert "vigentes o por vencer" in http.value.detail


def test_listado_y_descarga_no_dependen_del_estado(
    client, db, gestor, convenio, tmp_path
):
    soporte = _agregar_documento(db, convenio, tmp_path)
    convenio.estado = EstadoConvenio.VENCIDO.value
    db.commit()

    assert client.get(f"/api/convenios/{convenio.id}/documentos").status_code == 200
    descarga = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )
    assert descarga.status_code == 200


# ---- CA-04: carga por el endpoint ---------------------------------------------


@pytest.mark.parametrize(
    "estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER]
)
def test_endpoint_carga_soporte_en_convenio_activo(client, db, gestor, convenio, estado):
    convenio.estado = estado.value
    db.commit()

    respuesta = _cargar(client, convenio.id)

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo"] == "SOPORTE"


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.EN_TRAMITE,
        EstadoConvenio.VENCIDO,
        EstadoConvenio.RENOVADO,
        EstadoConvenio.FINALIZADO,
        EstadoConvenio.CANCELADO,
    ],
)
def test_endpoint_rechaza_carga_en_convenio_no_activo_con_422(
    client, db, gestor, convenio, tmp_path, estado
):
    convenio.estado = estado.value
    db.commit()
    documentos = select(func.count()).select_from(Documento).where(
        Documento.convenio_id == convenio.id
    )
    documentos_antes = db.scalar(documentos)
    archivos_antes = set((tmp_path / "documentos").rglob("*"))

    respuesta = _cargar(client, convenio.id)

    assert respuesta.status_code == 422
    assert "vigentes o por vencer" in respuesta.json()["detail"]
    # La regla se aplica antes de guardar: ni registro ni archivo nuevo.
    assert db.scalar(documentos) == documentos_antes
    assert set((tmp_path / "documentos").rglob("*")) == archivos_antes


def test_administrador_ori_puede_cargar_soportes(
    client, db, convenio, crear_usuario, entrar_como
):
    convenio.estado = EstadoConvenio.VIGENTE.value
    db.commit()
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    assert _cargar(client, convenio.id).status_code == 201


def test_carga_en_convenio_inexistente_responde_404(client, gestor):
    assert _cargar(client, 999_999_999).status_code == 404

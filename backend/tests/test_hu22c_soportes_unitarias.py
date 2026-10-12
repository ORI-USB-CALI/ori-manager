"""HU-22C — Pruebas unitarias de soportes de convenio (BE-03 y BE-04).

Sin base de datos ni HTTP: sesión y almacén son Mock y los objetos ORM se crean
en memoria. La integración con PostgreSQL y la API se cubre en
test_hu22c_soportes.py.
"""

import re
from datetime import UTC, datetime
from typing import get_args
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy.dialects import postgresql

from backend.api.routers import convenios as rutas
from backend.core.roles import CodigoRol
from backend.main import app
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import EstadoConvenio
from backend.models.rol import Rol
from backend.models.usuario import Usuario
from backend.schemas.soporte_convenio import SoporteConvenioLeer
from backend.services.convenios import ConvenioNoEncontrado, ErrorConvenio
from backend.services.documentos import ErrorAlmacenDocumentos
from backend.services.soportes_convenio import (
    ESTADOS_CARGA_SOPORTES,
    ConvenioNoAdmiteSoportes,
    ServicioSoportesConvenio,
    exigir_estado_carga_soportes,
)

# Enumerados a mano a propósito: derivarlos de ESTADOS_CARGA_SOPORTES haría el
# test auto-referencial y ampliar la regla por error no haría fallar nada.
ESTADOS_ACTIVOS = [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER]
ESTADOS_NO_ACTIVOS = [
    EstadoConvenio.EN_TRAMITE,
    EstadoConvenio.VENCIDO,
    EstadoConvenio.RENOVADO,
    EstadoConvenio.FINALIZADO,
    EstadoConvenio.CANCELADO,
]
PDF = b"%PDF-1.4\n% soporte unitario\n"
CREADO_EN = datetime(2026, 10, 1, 15, 30, tzinfo=UTC)


def _documento(**cambios) -> Documento:
    datos = {
        "id": 11,
        "convenio_id": 7,
        "tipo": "SOPORTE",
        "nombre_archivo": "Acta de inicio.pdf",
        "ruta_almacenamiento": "convenios/7/clave.pdf",
        "tipo_mime": "application/pdf",
        "tamano_bytes": len(PDF),
        "es_vigente": True,
        "creado_en": CREADO_EN,
        "cargado_por": Usuario(nombre_completo="Gestora ORI"),
    }
    return Documento(**(datos | cambios))


def _sql(sentencia) -> str:
    compilado = sentencia.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    return re.sub(r"\s+", " ", str(compilado))


# ---- Regla de estado (CA-04) --------------------------------------------------


@pytest.mark.parametrize("estado", ESTADOS_ACTIVOS)
def test_estado_activo_admite_carga(estado):
    exigir_estado_carga_soportes(Convenio(estado=estado.value))


@pytest.mark.parametrize("estado", ESTADOS_NO_ACTIVOS)
def test_estado_no_activo_rechaza_carga_con_mensaje_explicativo(estado):
    with pytest.raises(ConvenioNoAdmiteSoportes) as error:
        exigir_estado_carga_soportes(Convenio(estado=estado.value))

    assert estado.value in str(error.value)
    assert "vigentes o por vencer" in str(error.value)


def test_regla_cubre_exactamente_los_estados_activos():
    assert ESTADOS_CARGA_SOPORTES == set(ESTADOS_ACTIVOS)


def test_todo_estado_de_convenio_esta_clasificado():
    # Un estado nuevo hace fallar esta prueba y obliga a decidir si admite carga.
    assert set(ESTADOS_ACTIVOS) | set(ESTADOS_NO_ACTIVOS) == set(EstadoConvenio)
    assert not set(ESTADOS_ACTIVOS) & set(ESTADOS_NO_ACTIVOS)


def test_error_de_estado_es_un_error_de_convenio():
    # Los routers capturan ErrorConvenio; si no heredara, sería un 500.
    assert issubclass(ConvenioNoAdmiteSoportes, ErrorConvenio)


# ---- Esquema de respuesta (CA-03) ---------------------------------------------


def test_esquema_mapea_documento_al_contrato():
    soporte = SoporteConvenioLeer.desde_documento(_documento())

    assert soporte.model_dump() == {
        "id": 11,
        "nombre_original": "Acta de inicio.pdf",
        "tamano_bytes": len(PDF),
        "fecha_creacion": CREADO_EN,
        "usuario_nombre": "Gestora ORI",
    }


def test_esquema_sin_autor_deja_usuario_nombre_vacio():
    soporte = SoporteConvenioLeer.desde_documento(_documento(cargado_por=None))
    assert soporte.usuario_nombre is None


def test_esquema_serializa_fecha_iso_con_zona_horaria():
    json = SoporteConvenioLeer.desde_documento(_documento()).model_dump(mode="json")
    assert datetime.fromisoformat(json["fecha_creacion"]) == CREADO_EN


# ---- Servicio -----------------------------------------------------------------


@pytest.fixture
def db() -> Mock:
    return Mock()


@pytest.fixture
def almacen() -> Mock:
    return Mock()


@pytest.mark.parametrize("operacion", ["listar", "obtener_contenido", "verificar_carga"])
def test_convenio_inexistente_no_consulta_documentos_ni_almacen(db, almacen, operacion):
    db.get.return_value = None
    servicio = ServicioSoportesConvenio(db)
    argumentos = {
        "listar": (7,),
        "obtener_contenido": (7, 11, almacen),
        "verificar_carga": (7,),
    }[operacion]

    with pytest.raises(ConvenioNoEncontrado):
        getattr(servicio, operacion)(*argumentos)

    db.get.assert_called_once_with(Convenio, 7)
    db.scalars.assert_not_called()
    db.scalar.assert_not_called()
    almacen.leer.assert_not_called()


def test_verificar_carga_devuelve_el_convenio_activo(db):
    convenio = Convenio(id=7, estado=EstadoConvenio.VIGENTE.value)
    db.get.return_value = convenio

    assert ServicioSoportesConvenio(db).verificar_carga(7) is convenio


def test_verificar_carga_rechaza_convenio_no_activo(db):
    db.get.return_value = Convenio(id=7, estado=EstadoConvenio.CANCELADO.value)

    with pytest.raises(ConvenioNoAdmiteSoportes):
        ServicioSoportesConvenio(db).verificar_carga(7)


def test_listar_filtra_soportes_vigentes_del_convenio_y_ordena(db):
    db.get.return_value = Convenio(id=7)
    documentos = [_documento(id=12), _documento(id=11)]
    db.scalars.return_value = iter(documentos)

    resultado = ServicioSoportesConvenio(db).listar(7)

    assert resultado == documentos
    assert isinstance(resultado, list)
    sql = _sql(db.scalars.call_args.args[0])
    assert "documento.convenio_id = 7" in sql
    assert "documento.tipo = 'SOPORTE'" in sql
    assert "documento.es_vigente IS true" in sql
    assert "ORDER BY documento.creado_en DESC, documento.id DESC" in sql
    # El autor se carga en la misma consulta para armar usuario_nombre.
    assert "LEFT OUTER JOIN usuario" in sql


def test_obtener_contenido_lee_el_archivo_del_soporte(db, almacen):
    db.get.return_value = Convenio(id=7)
    documento = _documento()
    db.scalar.return_value = documento
    almacen.leer.return_value = PDF

    resultado = ServicioSoportesConvenio(db).obtener_contenido(7, 11, almacen)

    assert resultado == (documento, PDF)
    almacen.leer.assert_called_once_with("convenios/7/clave.pdf")
    sql = _sql(db.scalar.call_args.args[0])
    assert "documento.id = 11" in sql
    # Filtrar por convenio impide descargar soportes ajenos cambiando el id.
    assert "documento.convenio_id = 7" in sql
    assert "documento.tipo = 'SOPORTE'" in sql
    assert "documento.es_vigente IS true" in sql


def test_obtener_contenido_sin_soporte_no_lee_el_almacen(db, almacen):
    db.get.return_value = Convenio(id=7)
    db.scalar.return_value = None

    with pytest.raises(ConvenioNoEncontrado, match="Soporte no encontrado"):
        ServicioSoportesConvenio(db).obtener_contenido(7, 99, almacen)

    almacen.leer.assert_not_called()


def test_obtener_contenido_propaga_error_del_almacen(db, almacen):
    db.get.return_value = Convenio(id=7)
    db.scalar.return_value = _documento()
    almacen.leer.side_effect = ErrorAlmacenDocumentos("no disponible")

    with pytest.raises(ErrorAlmacenDocumentos):
        ServicioSoportesConvenio(db).obtener_contenido(7, 11, almacen)


# ---- Rutas como funciones (sin HTTP) ------------------------------------------


@pytest.fixture
def servicio(monkeypatch) -> Mock:
    falso = Mock()
    monkeypatch.setattr(rutas, "ServicioSoportesConvenio", Mock(return_value=falso))
    return falso


def test_ruta_listar_devuelve_el_contrato(servicio, db):
    servicio.listar.return_value = [_documento(), _documento(id=12, cargado_por=None)]

    resultado = rutas.listar_soportes(7, db, None)

    servicio.listar.assert_called_once_with(7)
    assert [item.id for item in resultado] == [11, 12]
    assert all(isinstance(item, SoporteConvenioLeer) for item in resultado)
    assert resultado[1].usuario_nombre is None


def test_ruta_listar_convenio_inexistente_responde_404(servicio, db):
    servicio.listar.side_effect = ConvenioNoEncontrado("Convenio no encontrado")

    with pytest.raises(HTTPException) as error:
        rutas.listar_soportes(7, db, None)

    assert error.value.status_code == 404


def test_ruta_descargar_por_defecto_es_adjunto_con_cabeceras_seguras(
    servicio, db, almacen
):
    servicio.obtener_contenido.return_value = (_documento(), PDF)

    respuesta = rutas.descargar_soporte(7, 11, db, almacen, None)

    servicio.obtener_contenido.assert_called_once_with(7, 11, almacen)
    assert respuesta.body == PDF
    assert respuesta.media_type == "application/pdf"
    assert respuesta.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''Acta%20de%20inicio.pdf"
    )
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["cache-control"] == "no-store"


def test_ruta_descargar_inline_codifica_tildes_y_enie(servicio, db, almacen):
    documento = _documento(nombre_archivo="Informe técnico Ñandú.pdf")
    servicio.obtener_contenido.return_value = (documento, PDF)

    respuesta = rutas.descargar_soporte(7, 11, db, almacen, None, disposicion="inline")

    assert respuesta.headers["content-disposition"] == (
        "inline; filename*=UTF-8''Informe%20t%C3%A9cnico%20%C3%91and%C3%BA.pdf"
    )


@pytest.mark.parametrize(
    ("error", "codigo"),
    [
        (ConvenioNoEncontrado("Soporte no encontrado para este convenio"), 404),
        (ErrorAlmacenDocumentos("no disponible"), 502),
    ],
)
def test_ruta_descargar_traduce_errores(servicio, db, almacen, error, codigo):
    servicio.obtener_contenido.side_effect = error

    with pytest.raises(HTTPException) as http:
        rutas.descargar_soporte(7, 11, db, almacen, None)

    assert http.value.status_code == codigo


def test_regla_de_estado_se_traduce_a_422():
    with pytest.raises(HTTPException) as http:
        rutas._lanzar_http(ConvenioNoAdmiteSoportes("Solo vigentes o por vencer"))

    assert http.value.status_code == 422
    assert http.value.detail == "Solo vigentes o por vencer"


# ---- Guard de permiso (CA-04) -------------------------------------------------


def _guard():
    # La misma función que FastAPI ejecuta en las dos rutas de soportes.
    return get_args(rutas.PuedeGestionarSoportes)[1].dependency


def _usuario(rol: CodigoRol) -> Usuario:
    return Usuario(id=1, rol=Rol(codigo=rol.value))


@pytest.mark.parametrize("rol", [CodigoRol.GESTOR_ORI, CodigoRol.ADMINISTRADOR_ORI])
def test_guard_permite_gestor_y_administrador(rol):
    usuario = _usuario(rol)
    assert _guard()(usuario) is usuario


@pytest.mark.parametrize(
    "rol",
    [CodigoRol.REVISOR_ORI, CodigoRol.SOLICITANTE_INTERNO, CodigoRol.SOLICITANTE_EXTERNO],
)
def test_guard_rechaza_otros_roles_con_403(rol):
    with pytest.raises(HTTPException) as error:
        _guard()(_usuario(rol))

    assert error.value.status_code == 403


# ---- Registro de rutas --------------------------------------------------------


@pytest.mark.parametrize(
    "ruta",
    [
        "/convenios/{convenio_id}/documentos",
        "/convenios/{convenio_id}/documentos/{documento_id}/descargar",
    ],
)
def test_rutas_registradas_como_get_y_protegidas_por_el_guard(ruta):
    # Se busca en el router de convenios: desde FastAPI 0.141 app.routes agrupa
    # los routers incluidos. El prefijo /api lo cubre la prueba de OpenAPI.
    registrada = next(
        r for r in rutas.router.routes if isinstance(r, APIRoute) and r.path == ruta
    )

    assert registrada.methods == {"GET"}
    dependencias = {dependencia.call for dependencia in registrada.dependant.dependencies}
    assert _guard() in dependencias


def test_openapi_restringe_disposicion_a_inline_y_attachment():
    operacion = app.openapi()["paths"][
        "/api/convenios/{convenio_id}/documentos/{documento_id}/descargar"
    ]["get"]
    parametro = next(p for p in operacion["parameters"] if p["name"] == "disposicion")

    assert parametro["required"] is False
    assert parametro["schema"]["enum"] == ["inline", "attachment"]
    assert parametro["schema"]["default"] == "attachment"

import pytest
from sqlalchemy import text

from backend.models.enums import RolUsuario
from backend.schemas.convenio import ConvenioCreate
from backend.services.convenio import crear_convenio, obtener_convenio
from backend.services.exceptions import (
    AliadoInvalidoError,
    ConvenioDuplicadoError,
    ConvenioNoEncontradoError,
    PermisoDenegadoError,
    SolicitudInvalidaError,
    UnidadOrganizacionalRequeridaError,
)


def insertar_solicitud(db, solicitud_id: int) -> None:
    db.execute(text("INSERT INTO solicitud_convenio (id) VALUES (:id)"), {"id": solicitud_id})
    db.commit()


def insertar_aliado(db, aliado_id: int) -> None:
    db.execute(text("INSERT INTO aliado (id) VALUES (:id)"), {"id": aliado_id})
    db.commit()


def _datos(**overrides) -> ConvenioCreate:
    base = {
        "solicitud_id": 1,
        "creado_por_id": 1,
        "aliado_id": None,
        "objeto": "Intercambio academico",
        "alcance": None,
        "unidad_organizacional_id": None,
    }
    base.update(overrides)
    return ConvenioCreate(**base)


# ---- CA-08: control de acceso ----------------------------------------


def test_crear_convenio_sin_permiso_no_modifica_nada(db_session):
    insertar_solicitud(db_session, 1)

    with pytest.raises(PermisoDenegadoError):
        crear_convenio(db_session, _datos(), rol=RolUsuario.SOLICITANTE_INTERNO)

    assert db_session.execute(text("SELECT COUNT(*) FROM convenio")).scalar() == 0


def test_consultar_convenio_sin_permiso(db_session):
    insertar_solicitud(db_session, 1)
    convenio = crear_convenio(db_session, _datos(), rol=RolUsuario.GESTOR_ORI)

    with pytest.raises(PermisoDenegadoError):
        obtener_convenio(db_session, convenio.id, rol=RolUsuario.SOLICITANTE_EXTERNO)


# ---- CA-01/CA-04: creacion y estado inicial ----------------------------


def test_crear_convenio_exitoso_queda_en_tramite(db_session):
    insertar_solicitud(db_session, 1)

    convenio = crear_convenio(db_session, _datos(), rol=RolUsuario.ADMINISTRADOR_ORI)

    assert convenio.id is not None
    assert convenio.estado == "EN_TRAMITE"
    assert convenio.creado_en is not None
    assert convenio.creado_por_id == 1


# ---- CA-02/CA-03: aliado opcional --------------------------------------


def test_crear_convenio_sin_aliado_es_valido(db_session):
    insertar_solicitud(db_session, 1)

    convenio = crear_convenio(db_session, _datos(aliado_id=None), rol=RolUsuario.GESTOR_ORI)

    assert convenio.aliado_id is None


def test_crear_convenio_con_aliado_existente(db_session):
    insertar_solicitud(db_session, 1)
    insertar_aliado(db_session, 5)

    convenio = crear_convenio(db_session, _datos(aliado_id=5), rol=RolUsuario.GESTOR_ORI)

    assert convenio.aliado_id == 5


# ---- CA-07: relaciones invalidas ---------------------------------------


def test_crear_convenio_con_solicitud_inexistente(db_session):
    with pytest.raises(SolicitudInvalidaError):
        crear_convenio(db_session, _datos(solicitud_id=999), rol=RolUsuario.GESTOR_ORI)


def test_crear_convenio_con_aliado_inexistente(db_session):
    insertar_solicitud(db_session, 1)

    with pytest.raises(AliadoInvalidoError):
        crear_convenio(db_session, _datos(aliado_id=999), rol=RolUsuario.GESTOR_ORI)


# ---- CA-05: identificador unico / no duplicar convenio por solicitud ---


def test_no_se_puede_duplicar_convenio_para_la_misma_solicitud(db_session):
    insertar_solicitud(db_session, 1)
    crear_convenio(db_session, _datos(), rol=RolUsuario.GESTOR_ORI)

    with pytest.raises(ConvenioDuplicadoError):
        crear_convenio(db_session, _datos(), rol=RolUsuario.GESTOR_ORI)


def test_dos_convenios_de_solicitudes_distintas_tienen_ids_distintos(db_session):
    insertar_solicitud(db_session, 1)
    insertar_solicitud(db_session, 2)

    convenio_1 = crear_convenio(db_session, _datos(solicitud_id=1), rol=RolUsuario.GESTOR_ORI)
    convenio_2 = crear_convenio(db_session, _datos(solicitud_id=2), rol=RolUsuario.GESTOR_ORI)

    assert convenio_1.id != convenio_2.id


# ---- Regla del MER: unidad_organizacional obligatoria si alcance=PROGRAMA


def test_alcance_programa_sin_unidad_organizacional_falla(db_session):
    insertar_solicitud(db_session, 1)

    with pytest.raises(UnidadOrganizacionalRequeridaError):
        crear_convenio(
            db_session,
            _datos(alcance="PROGRAMA", unidad_organizacional_id=None),
            rol=RolUsuario.GESTOR_ORI,
        )


def test_alcance_programa_con_unidad_organizacional_es_valido(db_session):
    insertar_solicitud(db_session, 1)

    convenio = crear_convenio(
        db_session,
        _datos(alcance="PROGRAMA", unidad_organizacional_id=7),
        rol=RolUsuario.GESTOR_ORI,
    )

    assert convenio.alcance == "PROGRAMA"
    assert convenio.unidad_organizacional_id == 7


# ---- CA-06: consulta ----------------------------------------------------


def test_obtener_convenio_no_encontrado(db_session):
    with pytest.raises(ConvenioNoEncontradoError):
        obtener_convenio(db_session, 12345, rol=RolUsuario.REVISOR_ORI)


def test_obtener_convenio_muestra_datos_almacenados(db_session):
    insertar_solicitud(db_session, 1)
    insertar_aliado(db_session, 5)
    creado = crear_convenio(db_session, _datos(aliado_id=5), rol=RolUsuario.GESTOR_ORI)

    consultado = obtener_convenio(db_session, creado.id, rol=RolUsuario.REVISOR_ORI)

    assert consultado.id == creado.id
    assert consultado.aliado_id == 5
    assert consultado.estado == "EN_TRAMITE"
    assert consultado.creado_por_id == 1

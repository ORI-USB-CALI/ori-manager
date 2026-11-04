import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import CodigoGuia, EstadoGuia
from backend.models.estado_guia_usuario import EstadoGuiaUsuario


def _solicitante(crear_usuario):
    return crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)


def _registrar(db, usuario, guia=CodigoGuia.ONBOARDING_INICIAL, estado=EstadoGuia.COMPLETADO, version=1):
    registro = EstadoGuiaUsuario(
        usuario_id=usuario.id, guia=guia, estado=estado, version=version
    )
    db.add(registro)
    db.commit()
    return registro


def test_tabla_estado_guia_usuario_tiene_columnas_y_restriccion_unica(db_engine):
    inspector = inspect(db_engine)
    columnas = {columna["name"] for columna in inspector.get_columns("estado_guia_usuario")}
    assert columnas == {
        "id", "usuario_id", "guia", "version", "estado", "creado_en", "actualizado_en",
    }
    unicas = {
        restriccion["name"]: restriccion["column_names"]
        for restriccion in inspector.get_unique_constraints("estado_guia_usuario")
    }
    assert unicas["uq_estado_guia_usuario_usuario_guia"] == ["usuario_id", "guia"]


@pytest.mark.parametrize("estado", [EstadoGuia.COMPLETADO, EstadoGuia.OMITIDO])
def test_guarda_estados_finales_con_version_y_fechas(db, crear_usuario, estado):
    usuario = _solicitante(crear_usuario)
    registro = _registrar(db, usuario, estado=estado, version=2)
    db.expire_all()
    guardado = db.get(EstadoGuiaUsuario, registro.id)
    assert guardado.usuario_id == usuario.id
    assert guardado.guia == CodigoGuia.ONBOARDING_INICIAL.value
    assert guardado.estado == estado.value
    assert guardado.version == 2
    assert guardado.creado_en is not None
    assert guardado.actualizado_en is not None


def test_no_permite_guardar_pendiente(db, crear_usuario):
    # RN-02/RN-03: PENDIENTE existe para la API, pero la ausencia de fila lo
    # representa; la base solo guarda estados finales.
    with pytest.raises(IntegrityError):
        _registrar(db, _solicitante(crear_usuario), estado=EstadoGuia.PENDIENTE)


def test_no_permite_guia_desconocida(db, crear_usuario):
    with pytest.raises(IntegrityError):
        _registrar(db, _solicitante(crear_usuario), guia="GUIA_INVENTADA")


def test_no_permite_version_menor_a_uno(db, crear_usuario):
    with pytest.raises(IntegrityError):
        _registrar(db, _solicitante(crear_usuario), version=0)


def test_no_permite_dos_estados_para_el_mismo_usuario_y_guia(db, crear_usuario):
    usuario = _solicitante(crear_usuario)
    _registrar(db, usuario, estado=EstadoGuia.OMITIDO)
    with pytest.raises(IntegrityError):
        _registrar(db, usuario, estado=EstadoGuia.COMPLETADO)


def test_estado_de_un_usuario_no_afecta_a_otro(db, crear_usuario):
    primero = _solicitante(crear_usuario)
    segundo = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    _registrar(db, primero, estado=EstadoGuia.COMPLETADO)
    _registrar(db, segundo, estado=EstadoGuia.OMITIDO)
    estados = dict(
        db.execute(
            select(EstadoGuiaUsuario.usuario_id, EstadoGuiaUsuario.estado).where(
                EstadoGuiaUsuario.usuario_id.in_([primero.id, segundo.id])
            )
        ).all()
    )
    assert estados == {primero.id: "COMPLETADO", segundo.id: "OMITIDO"}


def test_un_usuario_conserva_estados_independientes_por_guia(db, crear_usuario):
    # RN-06 / HU-39 RN-02: el onboarding y la guía de radicación no se mezclan.
    usuario = _solicitante(crear_usuario)
    _registrar(db, usuario, guia=CodigoGuia.ONBOARDING_INICIAL, estado=EstadoGuia.COMPLETADO)
    _registrar(db, usuario, guia=CodigoGuia.GUIA_RADICACION, estado=EstadoGuia.OMITIDO)
    estados = dict(
        db.execute(
            select(EstadoGuiaUsuario.guia, EstadoGuiaUsuario.estado).where(
                EstadoGuiaUsuario.usuario_id == usuario.id
            )
        ).all()
    )
    assert estados == {"ONBOARDING_INICIAL": "COMPLETADO", "GUIA_RADICACION": "OMITIDO"}

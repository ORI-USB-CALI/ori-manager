import pytest
from sqlalchemy.orm import Session

from backend.models.convenio import Convenio
from backend.models.enums import EstadoAliado, EstadoConvenio, RolUsuario, TipoAliado
from backend.services import aliado as aliado_service
from backend.services.exceptions import (
    AliadoConConveniosVigentesError,
    AliadoDuplicadoError,
    PermisoDenegadoError,
    SectorEconomicoRequeridoError,
)

ADMIN = RolUsuario.ADMINISTRADOR_ORI
GESTOR = RolUsuario.GESTOR_ORI
REVISOR = RolUsuario.REVISOR_ORI
SOLICITANTE = RolUsuario.SOLICITANTE_INTERNO


def _datos(identificacion: str = "900123456-1", **overrides: object) -> aliado_service.DatosAliado:
    base = {
        "identificacion": identificacion,
        "nombre": "Aliado de Prueba",
        "tipo": TipoAliado.EMPRESA,
        "sector_economico": "Tecnología",
    }
    base.update(overrides)
    return aliado_service.DatosAliado(**base)  # type: ignore[arg-type]


# CA-11 — Impedir duplicidad de aliados (y validación base de creación)
def test_crear_aliado_ok(db_session: Session) -> None:
    aliado = aliado_service.crear_aliado(db_session, _datos(), rol=GESTOR)

    assert aliado.id is not None
    assert aliado.estado == EstadoAliado.ACTIVO


def test_impide_duplicidad_de_aliados(db_session: Session) -> None:
    aliado_service.crear_aliado(db_session, _datos("900222222-2"), rol=ADMIN)

    with pytest.raises(AliadoDuplicadoError):
        aliado_service.crear_aliado(db_session, _datos("900222222-2"), rol=ADMIN)


def test_sector_economico_obligatorio_si_tipo_empresa(db_session: Session) -> None:
    datos = _datos(tipo=TipoAliado.EMPRESA, sector_economico=None)

    with pytest.raises(SectorEconomicoRequeridoError):
        aliado_service.crear_aliado(db_session, datos, rol=ADMIN)


# CA-12 — Restricción de gestión de aliados
def test_restriccion_de_gestion_para_roles_sin_permiso(db_session: Session) -> None:
    with pytest.raises(PermisoDenegadoError):
        aliado_service.crear_aliado(db_session, _datos("900333333-3"), rol=SOLICITANTE)


# CA-06 — Consultar aliado
def test_consultar_aliado_permitido_para_roles_ori(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900444444-4"), rol=ADMIN)

    encontrado = aliado_service.consultar_aliado(db_session, creado.id, rol=REVISOR)

    assert encontrado.id == creado.id


def test_consultar_aliado_denegado_para_roles_sin_permiso(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900555555-5"), rol=ADMIN)

    with pytest.raises(PermisoDenegadoError):
        aliado_service.consultar_aliado(db_session, creado.id, rol=SOLICITANTE)


# CA-07 — Editar información de un aliado
def test_editar_aliado_actualiza_datos_editables(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900666666-6"), rol=GESTOR)

    editado = aliado_service.editar_aliado(
        db_session,
        creado.id,
        aliado_service.DatosEdicionAliado(ciudad="Cali"),
        rol=GESTOR,
    )

    assert editado.ciudad == "Cali"


def test_editar_aliado_no_permite_cambiar_identificacion(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900777777-7"), rol=GESTOR)

    assert not hasattr(aliado_service.DatosEdicionAliado(), "identificacion")

    editado = aliado_service.editar_aliado(
        db_session,
        creado.id,
        aliado_service.DatosEdicionAliado(nombre="Nuevo Nombre"),
        rol=GESTOR,
    )

    assert editado.identificacion == "900777777-7"


# CA-08 / CA-09 — Inactivar aliado
def test_inactivar_aliado_sin_convenios_vigentes(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900888888-8"), rol=ADMIN)

    inactivado = aliado_service.inactivar_aliado(db_session, creado.id, rol=ADMIN)

    assert inactivado.estado == EstadoAliado.INACTIVO


def test_impide_inactivar_aliado_con_convenios_vigentes(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900999999-9"), rol=ADMIN)
    db_session.add(Convenio(aliado_id=creado.id, estado=EstadoConvenio.VIGENTE))
    db_session.flush()

    with pytest.raises(AliadoConConveniosVigentesError):
        aliado_service.inactivar_aliado(db_session, creado.id, rol=ADMIN)

    assert creado.estado == EstadoAliado.ACTIVO


# CA-10 — Reactivar aliado
def test_reactivar_aliado(db_session: Session) -> None:
    creado = aliado_service.crear_aliado(db_session, _datos("900101010-1"), rol=ADMIN)
    aliado_service.inactivar_aliado(db_session, creado.id, rol=ADMIN)

    reactivado = aliado_service.reactivar_aliado(db_session, creado.id, rol=ADMIN)

    assert reactivado.estado == EstadoAliado.ACTIVO


# CA-01 — Mantener solicitante mientras el convenio no esté activo
def test_no_crea_aliado_si_convenio_no_esta_vigente(db_session: Session) -> None:
    convenio = Convenio(estado=EstadoConvenio.EN_TRAMITE)
    db_session.add(convenio)
    db_session.flush()

    resultado = aliado_service.resolver_aliado_para_convenio(
        db_session, convenio, _datos("900202020-2")
    )

    assert resultado is None
    assert convenio.aliado_id is None
    assert aliado_service.buscar_por_identificacion(db_session, "900202020-2") is None


# CA-03 — Crear automáticamente un aliado por primera vez
def test_crea_aliado_automaticamente_al_activar_convenio(db_session: Session) -> None:
    convenio = Convenio(estado=EstadoConvenio.VIGENTE)
    db_session.add(convenio)
    db_session.flush()

    aliado = aliado_service.resolver_aliado_para_convenio(
        db_session, convenio, _datos("900303030-3", correo="contacto@aliado.com")
    )

    assert aliado is not None
    assert aliado.identificacion == "900303030-3"
    assert aliado.correo == "contacto@aliado.com"
    assert convenio.aliado_id == aliado.id


# CA-02 / CA-04 — Identificar y reutilizar un aliado existente
def test_reutiliza_aliado_existente_por_identificacion(db_session: Session) -> None:
    existente = aliado_service.crear_aliado(db_session, _datos("900404040-4"), rol=ADMIN)
    convenio = Convenio(estado=EstadoConvenio.VIGENTE)
    db_session.add(convenio)
    db_session.flush()

    aliado = aliado_service.resolver_aliado_para_convenio(
        db_session, convenio, _datos("900404040-4")
    )

    assert aliado is not None
    assert aliado.id == existente.id
    assert convenio.aliado_id == existente.id


# CA-05 — Manejar cambio de correo sin duplicar aliado
def test_actualiza_correo_de_aliado_existente_sin_duplicar(db_session: Session) -> None:
    existente = aliado_service.crear_aliado(
        db_session, _datos("900505050-5", correo="viejo@aliado.com"), rol=ADMIN
    )
    convenio = Convenio(estado=EstadoConvenio.VIGENTE)
    db_session.add(convenio)
    db_session.flush()

    aliado = aliado_service.resolver_aliado_para_convenio(
        db_session, convenio, _datos("900505050-5", correo="nuevo@aliado.com")
    )

    assert aliado is not None
    assert aliado.id == existente.id
    assert aliado.correo == "nuevo@aliado.com"

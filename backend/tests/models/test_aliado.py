import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.aliado import Aliado
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoAliado, EstadoConvenio, TipoAliado
from backend.models.pais import Pais


def _crear_aliado(db: Session, identificacion: str = "900123456-1") -> Aliado:
    aliado = Aliado(
        identificacion=identificacion,
        nombre="Universidad Ejemplo",
        tipo=TipoAliado.UNIVERSIDAD,
    )
    db.add(aliado)
    db.flush()
    return aliado


def test_aliado_estado_por_defecto_activo(db_session: Session) -> None:
    aliado = _crear_aliado(db_session)

    assert aliado.estado == EstadoAliado.ACTIVO


def test_aliado_identificacion_es_unica(db_session: Session) -> None:
    _crear_aliado(db_session, identificacion="900111111-1")
    db_session.flush()

    with pytest.raises(IntegrityError):
        _crear_aliado(db_session, identificacion="900111111-1")
        db_session.flush()


def test_pais_asociado_a_aliado(db_session: Session) -> None:
    pais = Pais(codigo_iso="CO", nombre="Colombia")
    db_session.add(pais)
    db_session.flush()

    aliado = _crear_aliado(db_session)
    aliado.pais_id = pais.id
    db_session.flush()

    assert aliado.pais_id == pais.id


def test_contacto_aliado_asociado_a_aliado(db_session: Session) -> None:
    aliado = _crear_aliado(db_session)

    contacto = ContactoAliado(
        aliado_id=aliado.id,
        nombre="Juana Pérez",
        es_principal=True,
    )
    db_session.add(contacto)
    db_session.flush()

    assert contacto.aliado_id == aliado.id
    assert contacto.es_principal is True
    assert contacto.activo is True


def test_convenio_estado_por_defecto_en_tramite(db_session: Session) -> None:
    convenio = Convenio()
    db_session.add(convenio)
    db_session.flush()

    assert convenio.estado == EstadoConvenio.EN_TRAMITE
    assert convenio.aliado_id is None


def test_convenio_puede_asociarse_a_un_aliado(db_session: Session) -> None:
    aliado = _crear_aliado(db_session)

    convenio = Convenio(aliado_id=aliado.id, estado=EstadoConvenio.VIGENTE)
    db_session.add(convenio)
    db_session.flush()

    assert convenio.aliado_id == aliado.id

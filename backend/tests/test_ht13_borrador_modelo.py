import pytest
from sqlalchemy.exc import IntegrityError

from backend.models.borrador_convenio import BorradorConvenio

CONTENIDO = {"type": "doc", "content": [{"type": "paragraph"}]}


def _borrador(convenio, usuario, revision: int = 1) -> BorradorConvenio:
    return BorradorConvenio(
        convenio_id=convenio.id,
        contenido=CONTENIDO,
        revision=revision,
        actualizado_por_id=usuario.id,
    )


def test_el_borrador_se_guarda_aparte_sin_cambiar_la_version(
    db, gestor, convenio_listo
) -> None:
    version = convenio_listo.version_actual
    db.add(_borrador(convenio_listo, gestor))
    db.commit()
    db.expire_all()

    assert convenio_listo.borrador.contenido == CONTENIDO
    assert convenio_listo.borrador.revision == 1
    assert convenio_listo.version_actual == version


def test_un_convenio_tiene_un_solo_borrador(db, gestor, convenio_listo) -> None:
    db.add(_borrador(convenio_listo, gestor))
    db.commit()

    db.add(_borrador(convenio_listo, gestor))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_la_revision_del_borrador_es_positiva(db, gestor, convenio_listo) -> None:
    db.add(_borrador(convenio_listo, gestor, revision=0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

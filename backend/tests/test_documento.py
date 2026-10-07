from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.solicitud_convenio import SolicitudConvenio


def _documento(**campos) -> Documento:
    valores = {
        "tipo": "BORRADOR",
        "nombre_archivo": "borrador.pdf",
        "ruta_almacenamiento": f"pruebas/{uuid4().hex}.pdf",
        "tipo_mime": "application/pdf",
        "tamano_bytes": 10,
    }
    valores.update(campos)
    return Documento(**valores)


def test_documento_admite_asociacion_a_solicitud_y_convenio(db, crear_usuario):
    usuario = crear_usuario(
        CodigoRol.SOLICITANTE_INTERNO, tipo_usuario=TipoUsuario.INTERNO
    )
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex}",
        tipo_solicitante="INTERNO",
        solicitante_id=usuario.id,
        estado="BORRADOR",
    )
    db.add(solicitud)
    db.flush()
    convenio = Convenio(
        solicitud_id=solicitud.id,
        creado_por_id=usuario.id,
        estado="EN_TRAMITE",
    )
    db.add(convenio)
    db.flush()

    documento_solicitud = _documento(tipo="OTRO_SOPORTE", solicitud_id=solicitud.id)
    documento_convenio = _documento(
        tipo="FORMATO_SOLICITUD", convenio_id=convenio.id
    )
    documento_compartido = _documento(
        solicitud_id=solicitud.id, convenio_id=convenio.id
    )
    db.add_all([documento_solicitud, documento_convenio, documento_compartido])
    db.flush()

    assert documento_solicitud in solicitud.documentos
    assert documento_convenio in convenio.documentos
    assert documento_compartido.solicitud_id == solicitud.id
    assert documento_compartido.convenio_id == convenio.id


def test_documento_exige_solicitud_o_convenio(db):
    with (
        pytest.raises(IntegrityError, match="ck_documento_solicitud_o_convenio"),
        db.begin_nested(),
    ):
        db.add(_documento())
        db.flush()

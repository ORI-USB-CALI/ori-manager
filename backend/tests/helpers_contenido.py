"""Documentos elaborados para escenarios que deben superar Elaboracion."""
from copy import deepcopy

from sqlalchemy import select

from backend.models.borrador_convenio import BorradorConvenio


def documento_contractual(texto="Las partes acuerdan cooperar en actividades academicas."):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": texto}
    ]}]}


def preparar_documento_contractual(db, convenio):
    """Preparacion explicita de fixture; no altera versiones ni la solicitud."""
    borrador = db.scalar(select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio.id))
    assert borrador is not None
    borrador.contenido = deepcopy(documento_contractual())
    db.commit()

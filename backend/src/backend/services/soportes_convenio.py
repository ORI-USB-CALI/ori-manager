"""Consulta, descarga y regla de carga de soportes de convenios (HU-22C)."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import EstadoConvenio
from backend.services.convenios import (
    ESTADOS_CARGA_SOPORTES,
    ConvenioNoAdmiteSoportes,
    ConvenioNoEncontrado,
    ErrorConvenio,
)
from backend.services.documentos import AlmacenDocumentos

TIPO_DOCUMENTO_SOPORTE = "SOPORTE"


def exigir_estado_carga_soportes(convenio: Convenio) -> None:
    """Regla de CA-04. Aplica solo a la carga: listar y descargar soportes se
    permite en cualquier estado para consultar convenios vencidos o finalizados."""
    if convenio.estado not in ESTADOS_CARGA_SOPORTES:
        raise ConvenioNoAdmiteSoportes(
            "Solo se pueden cargar soportes en convenios vigentes o por vencer; "
            f"el convenio está en estado {convenio.estado}"
        )


class ServicioSoportesConvenio:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _obtener_convenio(self, convenio_id: int) -> Convenio:
        convenio = self.db.get(Convenio, convenio_id)
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def verificar_carga(self, convenio_id: int) -> Convenio:
        """Punto de entrada de la regla de estado para el endpoint de carga."""
        convenio = self._obtener_convenio(convenio_id)
        exigir_estado_carga_soportes(convenio)
        return convenio

    def listar(self, convenio_id: int) -> list[Documento]:
        self._obtener_convenio(convenio_id)
        return list(
            self.db.scalars(
                select(Documento)
                .options(joinedload(Documento.cargado_por))
                .where(
                    Documento.convenio_id == convenio_id,
                    Documento.tipo == TIPO_DOCUMENTO_SOPORTE,
                    Documento.es_vigente.is_(True),
                )
                .order_by(Documento.creado_en.desc(), Documento.id.desc())
            )
        )

    def obtener_contenido(
        self, convenio_id: int, documento_id: int, almacen: AlmacenDocumentos
    ) -> tuple[Documento, bytes]:
        self._obtener_convenio(convenio_id)
        # Filtrar por convenio impide descargar soportes de otro convenio
        # cambiando solo el id del documento en la URL.
        documento = self.db.scalar(
            select(Documento).where(
                Documento.id == documento_id,
                Documento.convenio_id == convenio_id,
                Documento.tipo == TIPO_DOCUMENTO_SOPORTE,
                Documento.es_vigente.is_(True),
            )
        )
        if documento is None:
            raise ConvenioNoEncontrado("Soporte no encontrado para este convenio")
        return documento, almacen.leer(documento.ruta_almacenamiento)

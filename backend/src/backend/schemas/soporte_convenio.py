from datetime import datetime

from pydantic import BaseModel

from backend.models.documento import Documento


class SoporteConvenioLeer(BaseModel):
    """Soporte adjunto a un convenio, con el contrato de CA-03 de HU-22C."""

    id: int
    nombre_original: str
    tamano_bytes: int
    fecha_creacion: datetime
    usuario_nombre: str | None = None

    @classmethod
    def desde_documento(cls, documento: Documento) -> "SoporteConvenioLeer":
        return cls(
            id=documento.id,
            nombre_original=documento.nombre_archivo,
            tamano_bytes=documento.tamano_bytes,
            fecha_creacion=documento.creado_en,
            usuario_nombre=(
                documento.cargado_por.nombre_completo
                if documento.cargado_por is not None
                else None
            ),
        )

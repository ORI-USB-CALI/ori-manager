from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Representación explícita de un dato ausente en el PDF y el Excel. Un dato
# que falta nunca se reemplaza por un valor supuesto.
INFORMACION_NO_DISPONIBLE = "Información no disponible"


# Marca visible de los documentos de trabajo, antes de formalizar el convenio.
MARCA_BORRADOR = "BORRADOR — NO FORMALIZADO"

# HT-06, CA-01 y CA-07: el documento de trabajo no anuncia un "código oficial"
# que todavía no existe. Lleva una referencia provisional, derivada del
# identificador interno del convenio (RN-10), distinguible del código
# institucional aprobado.
ETIQUETA_CODIGO_OFICIAL = "Código oficial"
ETIQUETA_REFERENCIA_PROVISIONAL = "Identificación provisional"


def referencia_provisional(convenio_id: int) -> str:
    return f"Convenio provisional #{convenio_id}"


class FormatoExportacion(StrEnum):
    PDF = "pdf"
    EXCEL = "excel"


class ModoEmision(StrEnum):
    """Lo determina el backend a partir del convenio, nunca el cliente."""

    BORRADOR = "BORRADOR"
    OFICIAL = "OFICIAL"


class FirmantePdfDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    orden: int
    rol: str
    parte: str
    nombre: str
    cargo: str
    modalidad: str
    estado: str


class SeccionContenidoDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    tipo: str  # "heading" | "paragraph" | "list_item"
    nivel: int = 1
    # Texto plano, tal como lo escribió el usuario (Excel).
    texto: str
    # Mismo texto escapado, con solo el marcado válido del documento (PDF).
    texto_formateado: str


class ConvenioPdfDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    convenio_id: int
    # Obligatorio y sin valor por defecto: cada exportación declara su modo.
    modo_emision: ModoEmision
    codigo: str | None
    solicitud_consecutivo: str
    tipo_convenio: str
    estado: str
    etapa: str
    alcance: str
    objeto: str
    justificacion: str
    implicacion_financiera: str
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    duracion_meses: int | None
    porcentaje_avance: int | None
    version_actual: int
    fecha_emision: datetime = Field(default_factory=datetime.utcnow)

    # Partes
    solicitante_nombre: str
    solicitante_correo: str
    solicitante_unidad: str
    solicitante_tipo: str

    aliado_nombre: str
    aliado_tipo: str
    aliado_identificacion: str
    aliado_pais: str
    aliado_ciudad: str
    aliado_contacto_nombre: str
    aliado_contacto_correo: str

    # Cláusulas / Contenido estructurado
    secciones_contenido: list[SeccionContenidoDTO] = Field(default_factory=list)

    # Firmantes oficiales
    firmantes: list[FirmantePdfDTO] = Field(default_factory=list)

    def identificacion(self) -> tuple[str, str | None]:
        """Etiqueta y valor con que el documento identifica al convenio.

        Vive aquí para que el PDF y el Excel digan lo mismo. El documento
        oficial lleva el código institucional; el de trabajo, la referencia
        provisional (HT-06, CA-01 y CA-07).
        """
        if self.modo_emision is ModoEmision.OFICIAL:
            return ETIQUETA_CODIGO_OFICIAL, self.codigo
        return ETIQUETA_REFERENCIA_PROVISIONAL, referencia_provisional(
            self.convenio_id
        )

"""Servicio de orquestación de exportación de convenios (PDF / Excel).

Maneja la validación de integridad previa a la exportación (CA-03)
y el despacho al generador correspondiente (PDF o Excel).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.convenio import Convenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.schemas.exportacion import FormatoExportacion
from backend.services.convenios import ConvenioNoEncontrado, ErrorConvenio
from backend.services.excel_convenio import ServicioExcelConvenio
from backend.services.pdf_convenio import ServicioPdfConvenio
from backend.services.validador_exportacion_convenio import ConvenioExportValidator

MENSAJE_CONVENIO_INCOMPLETO = (
    "No es posible generar el documento oficial. Faltan datos obligatorios."
)


class ErrorValidacionExportacion(ErrorConvenio):
    """El convenio no tiene los datos obligatorios para un documento oficial (CA-03)."""

    codigo = "CONVENIO_INCOMPLETO"

    def __init__(self, campos_faltantes: list[str]) -> None:
        self.campos_faltantes = campos_faltantes
        super().__init__(MENSAJE_CONVENIO_INCOMPLETO)

    def como_respuesta(self) -> dict[str, object]:
        return {
            "error": self.codigo,
            "message": str(self),
            "campos_faltantes": self.campos_faltantes,
        }


class ServicioExportacionConvenio:
    """Orquestador de exportación para convenios institucionales."""

    def __init__(
        self,
        servicio_pdf: ServicioPdfConvenio | None = None,
        servicio_excel: ServicioExcelConvenio | None = None,
    ) -> None:
        self.servicio_pdf = servicio_pdf or ServicioPdfConvenio()
        self.servicio_excel = servicio_excel or ServicioExcelConvenio()

    def validar_para_exportacion(self, convenio_id: int, db: Session) -> Convenio:
        """Valida que el convenio exista y contenga los datos esenciales para emitir un documento oficial (CA-03)."""
        stmt = (
            select(Convenio)
            .options(
                joinedload(Convenio.tipo_convenio),
                joinedload(Convenio.unidad_organizacional),
                joinedload(Convenio.aliado),
                selectinload(Convenio.solicitud),
                selectinload(Convenio.versiones),
                selectinload(Convenio.procesos_firmas).selectinload(
                    ProcesoFirmasConvenio.firmas
                ),
            )
            .where(Convenio.id == convenio_id)
        )
        convenio = db.scalar(stmt)
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")

        # Se valida antes de renderizar: un convenio incompleto no llega a
        # generar ni a guardar ningún archivo.
        faltantes = ConvenioExportValidator().campos_faltantes(convenio)
        if faltantes:
            raise ErrorValidacionExportacion(faltantes)

        return convenio

    def exportar(
        self,
        convenio_id: int,
        formato: FormatoExportacion | str,
        db: Session,
    ) -> tuple[bytes, str, str]:
        """Orquesta la validación y generación del archivo en el formato seleccionado.

        Retorna:
            tuple[bytes, str, str]: (contenido_bytes, media_type, filename)
        """
        # 1. Validar integridad de datos (CA-03)
        convenio = self.validar_para_exportacion(convenio_id, db)

        # 2. Construir nombre seguro de archivo
        raw_codigo = (convenio.codigo or f"ID-{convenio.id}").strip()
        codigo_seguro = re.sub(r"[^\w\-.]", "_", raw_codigo)
        fecha_actual = datetime.now(UTC).date().isoformat()

        # 3. Normalizar formato
        formato_str = (
            str(formato.value if isinstance(formato, FormatoExportacion) else formato)
            .lower()
            .strip()
        )

        if formato_str == FormatoExportacion.PDF.value:
            contenido = self.servicio_pdf.generar_pdf(convenio_id, db)
            filename = f"Convenio_{codigo_seguro}_{fecha_actual}.pdf"
            media_type = "application/pdf"
            return contenido, media_type, filename

        if formato_str == FormatoExportacion.EXCEL.value:
            contenido = self.servicio_excel.generar_excel(convenio_id, db)
            filename = f"Convenio_{codigo_seguro}_{fecha_actual}.xlsx"
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            return contenido, media_type, filename

        raise ValueError(f"Formato no soportado: {formato_str}")
